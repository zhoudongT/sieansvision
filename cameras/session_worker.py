"""Persistent SDK connection, bounded line protocol and graceful stdin stop.

t245u: stdin also accepts pace/idle commands so warm freerun without a consumer
stops flooding JPEG lines into engine-host (drop-old still drained the pipe →
no backpressure → multi-hour 卡 / GNOME 无响应).
"""
import json
import os
import sys
import threading
import time

output = os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding='utf-8')
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
stopped = threading.Event()
_pace_lock = threading.Lock()
# seconds between sends; idle skips JPEG and emits heartbeat only
_pace_interval_s = 0.1
_idle = False
_last_heartbeat_mono = 0.0
_encode_flag = {'on': True}


def send(message):
    line = json.dumps(message, ensure_ascii=False, allow_nan=False)
    if len(line.encode('utf-8')) > 35_000_000:
        raise ValueError('相机帧超过 35 MB，请降低分辨率或增加点云采样步长')
    output.write(line+'\n')
    output.flush()  # Pipe backpressure prevents an unbounded output queue.


def _set_pace(interval_ms, idle=False):
    global _pace_interval_s, _idle
    ms = int(interval_ms)
    ms = max(50, min(60_000, ms))
    with _pace_lock:
        _pace_interval_s = ms / 1000.0
        _idle = bool(idle)
        _encode_flag['on'] = not _idle


def _get_pace():
    with _pace_lock:
        return _pace_interval_s, _idle


def watch_commands():
    # EOF, stop, or invalid control input stop acquisition.
    # t245u: {"cmd":"pace","intervalMs":1000,"idle":true} slows/skips JPEG flood.
    while not stopped.is_set():
        line = sys.stdin.readline(110_001)
        if not line:
            stopped.set()
            return
        text = line.strip()
        if not text or text == 'stop':
            stopped.set()
            return
        try:
            msg = json.loads(text)
        except Exception:
            stopped.set()
            return
        if not isinstance(msg, dict):
            stopped.set()
            return
        cmd = msg.get('cmd') or msg.get('command')
        if cmd == 'pace':
            _set_pace(msg.get('intervalMs') or 100, idle=bool(msg.get('idle')))
            continue
        # stop / unknown → end session (compat with stdin.end('stop\n'))
        stopped.set()
        return


def main():
    from adapter import config, capture_frames
    request = json.loads(sys.stdin.readline(110_001))
    params = dict(request['params'])
    interval_ms = int(request['intervalMs'])
    _set_pace(interval_ms, idle=False)
    # GenTL freerun must not outpace session pulls: producer-faster fills the
    # ring → incomplete top-strip / bottom-zero frames (is_complete still True).
    # Tie device rate to ≤0.9× pull rate; leave buffers for JPEG jitter.
    if params.get('driver') == 'gentl' and params.get('trigger', 'freerun') == 'freerun':
        if 'acquisitionFrameRate' not in params:
            params['acquisitionFrameRate'] = round(
                max(1.0, min(15.0, 900.0 / max(interval_ms, 50))), 2)
        if 'previewBufferCount' not in params:
            params['previewBufferCount'] = 16
    p = config(params)
    attempts = request['reconnectAttempts']
    reconnect = request['reconnectMs']/1000
    if p['driver'] == 'gentl':
        # Prefer C++ GenTLCapture when available; still warm harvesters import
        # so fallback works without delaying the first reconnect.
        prefer_native = False
        try:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if root not in sys.path:
                sys.path.insert(0, root)
            pydeps = os.path.join(root, '.pydeps')
            if pydeps not in sys.path:
                sys.path.insert(0, pydeps)
            from vision import native_bridge
            prefer_native = bool(native_bridge.gentl_acquire_preferred())
        except Exception as exc:
            sys.stderr.write(f'[sieans] GenTL native prefer probe: {exc}\n')
        sys.stderr.write(
            f'[sieans] GenTL session acquire='
            f'{"sieans_native" if prefer_native else "harvesters"}\n'
        )
        sys.stderr.flush()
        if not prefer_native:
            # Harvesters' version discovery can spawn Git on import. On Windows,
            # starting it after a thread blocks on the inherited stdin pipe can
            # stall import. Finish this dependency initialization before watch.
            from harvesters.core import Harvester  # noqa: F401
    threading.Thread(target=watch_commands, daemon=True).start()
    retries = 0
    while not stopped.is_set():
        frames = capture_frames(p, encode_flag=_encode_flag)
        try:
            while not stopped.is_set():
                started = time.monotonic()
                interval, idle = _get_pace()
                if idle:
                    # Drain GenTL/UVC (encode_flag off → no JPEG) so buffers do
                    # not fill; heartbeat-only to Node (t245u long-run hang fix).
                    try:
                        next(frames)  # None when encode off
                    except Exception:
                        if stopped.is_set():
                            break
                        raise
                    global _last_heartbeat_mono
                    now = time.monotonic()
                    if now - _last_heartbeat_mono >= max(0.8, interval):
                        send(dict(event='heartbeat', at=int(time.time() * 1000)))
                        _last_heartbeat_mono = now
                    # t249u: was min(interval, 0.1) → native GenTL grab+np.copy at 10 Hz
                    # even when idle/heartbeat-only (session_worker ~28% CPU). With
                    # LatestImagesOnly, drain once per idle interval is enough.
                    drain = max(0.2, float(interval) if interval else 1.0)
                    stopped.wait(max(0, drain - (time.monotonic() - started)))
                    continue
                else:
                    data = next(frames)
                    if stopped.is_set():
                        break
                    if data is None:
                        continue
                    send(dict(event='frame', data=data))
                # Reconnect budget is per session, not reset by intermittent
                # successes; faulty devices cannot retry forever.
                stopped.wait(max(0, interval - (time.monotonic() - started)))
            return
        except Exception as error:
            if stopped.is_set():
                return
            if retries >= attempts:
                raise
            retries += 1
            send(dict(event='reconnecting', attempt=retries, error=str(error)[:1000]))
        finally:
            frames.close()
        if stopped.wait(reconnect):
            return


try:
    main()
except Exception as error:
    try:
        send(dict(event='error', error=str(error)[:2000] or type(error).__name__))
    except Exception:
        pass
    sys.exit(1)
finally:
    output.close()
