"""Local stand-in for 云同步 / 远程模板市场.

File-backed HTTP API on 127.0.0.1 (default :19779):
  GET  /health
  GET  /api/templates          → list [{name,meta,bytes,mtime}]
  GET  /api/templates/<file>   → raw JSON body
  POST /api/templates          → publish {filename?, meta?, ...snapshot}
  DELETE /api/templates/<file> → remove published copy (seed folder untouched unless force)

Catalog roots (merged, publish writes to data root):
  1) projects/run-ui-templates   (seed / industry)
  2) <data>/template-market      (user published / synced)
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 19779

_lock = threading.Lock()
_state = {
    'server': None,
    'thread': None,
    'host': DEFAULT_HOST,
    'port': DEFAULT_PORT,
    'seed': None,
    'store': None,
}


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def configure(seed_dir: Path | str | None = None, store_dir: Path | str | None = None,
              host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    with _lock:
        if seed_dir is not None:
            _state['seed'] = Path(seed_dir)
        if store_dir is not None:
            _state['store'] = Path(store_dir)
        _state['host'] = host
        _state['port'] = int(port)


def _dirs():
    seed = _state.get('seed')
    store = _state.get('store')
    dirs = []
    if seed:
        Path(seed).mkdir(parents=True, exist_ok=True)
        dirs.append(Path(seed))
    if store:
        Path(store).mkdir(parents=True, exist_ok=True)
        dirs.append(Path(store))
    return dirs


def _safe_name(name: str) -> str:
    name = (name or '').strip().replace('\\', '/').split('/')[-1]
    if not name or name.startswith('.'):
        raise ValueError('非法模板名')
    if not (name.endswith('.ruitpl.json') or name.endswith('.json')):
        name = f'{name}.ruitpl.json'
    # strip path tricks
    if '..' in name or '/' in name:
        raise ValueError('非法模板名')
    return name


def list_templates():
    seen = {}
    for folder in _dirs():
        for f in sorted(folder.glob('*.ruitpl.json')) + sorted(folder.glob('*.json')):
            if f.name in seen:
                continue
            meta = {}
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                meta = data.get('meta') or {}
            except Exception:
                data = None
            seen[f.name] = {
                'name': f.name,
                'title': meta.get('name') or f.stem,
                'scenario': meta.get('scenario') or '',
                'author': meta.get('author') or '',
                'description': meta.get('description') or '',
                'bytes': f.stat().st_size,
                'mtime': datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(timespec='seconds'),
                'source': str(folder),
                'origin': 'seed' if folder == _state.get('seed') else 'store',
            }
    return list(seen.values())


def read_template(name: str) -> tuple[str, dict]:
    name = _safe_name(name)
    for folder in _dirs():
        path = folder / name
        if path.is_file():
            raw = path.read_text(encoding='utf-8')
            return raw, json.loads(raw)
    raise FileNotFoundError(name)


def publish_template(payload: dict, filename: str | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('payload 必须为 JSON 对象')
    store = _state.get('store')
    if store is None:
        # fall back to seed if only one root
        dirs = _dirs()
        if not dirs:
            raise RuntimeError('未配置模板目录')
        store = dirs[-1]
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    meta = dict(payload.get('meta') or {})
    if filename:
        name = _safe_name(filename)
    else:
        title = meta.get('name') or payload.get('name') or 'run_ui'
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in str(title))[:40]
        name = _safe_name(f'{safe or "run_ui"}.ruitpl.json')
    meta.setdefault('syncedAt', _now())
    meta.setdefault('source', 'local-market')
    payload = dict(payload)
    payload['meta'] = meta
    if 'format' not in payload:
        payload['format'] = 'sieans.runUiTemplate'
    path = store / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'name': name, 'path': str(path), 'meta': meta}


def delete_template(name: str, *, allow_seed: bool = False) -> bool:
    name = _safe_name(name)
    store = _state.get('store')
    if store:
        path = Path(store) / name
        if path.is_file():
            path.unlink()
            return True
    if allow_seed and _state.get('seed'):
        path = Path(_state['seed']) / name
        if path.is_file():
            path.unlink()
            return True
    return False


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):  # quiet
        return

    def _send(self, code: int, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, (dict, list)):
            raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            raw = body.encode('utf-8')
        else:
            raw = body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b'{}'
        return json.loads(raw.decode('utf-8') or '{}')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ('/health', '/api/health'):
                return self._send(200, {
                    'ok': True, 'service': 'sieans-template-market-local',
                    'host': _state['host'], 'port': _state['port'],
                    'count': len(list_templates()), 'time': _now(),
                })
            if path in ('/api/templates', '/api/templates/'):
                return self._send(200, {'ok': True, 'templates': list_templates()})
            if path.startswith('/api/templates/'):
                name = unquote(path[len('/api/templates/'):])
                raw, data = read_template(name)
                return self._send(200, raw if self.headers.get('Accept') == 'application/octet-stream' else data)
            return self._send(404, {'ok': False, 'error': 'not found'})
        except FileNotFoundError:
            return self._send(404, {'ok': False, 'error': 'template not found'})
        except Exception as err:
            return self._send(500, {'ok': False, 'error': str(err)})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path in ('/api/templates', '/api/templates/'):
                payload = self._read_json()
                filename = payload.pop('filename', None) if isinstance(payload, dict) else None
                # allow wrap {filename, template:{...}}
                if isinstance(payload, dict) and 'template' in payload and isinstance(payload['template'], dict):
                    filename = payload.get('filename') or filename
                    payload = payload['template']
                info = publish_template(payload, filename=filename)
                return self._send(201, {'ok': True, **info})
            if path in ('/api/sync', '/api/sync/'):
                # "cloud sync" stand-in: re-list + touch syncedAt on store copies
                items = list_templates()
                return self._send(200, {'ok': True, 'synced': len(items), 'templates': items, 'time': _now()})
            return self._send(404, {'ok': False, 'error': 'not found'})
        except Exception as err:
            return self._send(400, {'ok': False, 'error': str(err)})

    def do_DELETE(self):
        path = urlparse(self.path).path
        try:
            if path.startswith('/api/templates/'):
                name = unquote(path[len('/api/templates/'):])
                ok = delete_template(name)
                return self._send(200 if ok else 404, {'ok': ok, 'name': name})
            return self._send(404, {'ok': False, 'error': 'not found'})
        except Exception as err:
            return self._send(400, {'ok': False, 'error': str(err)})


def _status_unlocked() -> dict:
    srv = _state['server']
    running = bool(srv is not None)
    return {
        'running': running,
        'host': _state['host'],
        'port': _state['port'],
        'url': f"http://{_state['host']}:{_state['port']}",
        'seed': str(_state['seed']) if _state['seed'] else None,
        'store': str(_state['store']) if _state['store'] else None,
        'count': len(list_templates()) if (_state['seed'] or _state['store']) else 0,
    }


def status() -> dict:
    with _lock:
        return _status_unlocked()


def start(seed_dir=None, store_dir=None, host=None, port=None) -> dict:
    with _lock:
        if seed_dir is not None:
            _state['seed'] = Path(seed_dir)
        if store_dir is not None:
            _state['store'] = Path(store_dir)
        if host is not None:
            _state['host'] = host
        if port is not None:
            _state['port'] = int(port)
        if _state['server'] is not None:
            return _status_unlocked()
        if _state['seed'] is None and _state['store'] is None:
            raise RuntimeError('configure seed/store before start')
        _dirs()
        httpd = ThreadingHTTPServer((_state['host'], _state['port']), _Handler)
        httpd.daemon_threads = True
        th = threading.Thread(target=httpd.serve_forever, name='sieans-template-market', daemon=True)
        _state['server'] = httpd
        _state['thread'] = th
        th.start()
        return _status_unlocked()


def stop() -> dict:
    with _lock:
        srv = _state['server']
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass
            try:
                srv.server_close()
            except Exception:
                pass
        _state['server'] = None
        _state['thread'] = None
        return _status_unlocked()


def client_list(base_url: str | None = None, timeout=2.0):
    import urllib.request
    url = (base_url or status()['url']).rstrip('/') + '/api/templates'
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def client_download(name: str, base_url: str | None = None, timeout=2.0) -> dict:
    import urllib.request
    from urllib.parse import quote
    url = (base_url or status()['url']).rstrip('/') + '/api/templates/' + quote(name)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def client_publish(payload: dict, filename: str | None = None, base_url: str | None = None, timeout=2.0) -> dict:
    import urllib.request
    url = (base_url or status()['url']).rstrip('/') + '/api/templates'
    body = dict(payload)
    if filename:
        body = {'filename': filename, 'template': payload}
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def client_sync(base_url: str | None = None, timeout=2.0) -> dict:
    import urllib.request
    url = (base_url or status()['url']).rstrip('/') + '/api/sync'
    req = urllib.request.Request(url, data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='SIEANS local template market')
    ap.add_argument('--seed', type=Path, default=Path('projects/run-ui-templates'))
    ap.add_argument('--store', type=Path, default=Path('data/native-desktop/template-market'))
    ap.add_argument('--host', default=DEFAULT_HOST)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    configure(args.seed, args.store, args.host, args.port)
    info = start()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print(json.dumps(stop(), ensure_ascii=False))
