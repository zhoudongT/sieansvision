"""One trusted user script per child process. A timeout is not a security sandbox."""
import contextlib
import json
import sys
import time
import traceback
from pathlib import Path as _Path
_root = _Path(__file__).resolve().parent.parent
_pydeps = _root / ".pydeps"
if _pydeps.is_dir() and str(_pydeps) not in sys.path:
    sys.path.insert(0, str(_pydeps))


class Log:
    def __init__(self):
        self.text = ''

    def write(self, text):
        self.text = (self.text + str(text))[-8000:]
        return len(text)

    def flush(self):
        pass


def main():
    request = json.load(sys.stdin)
    code = request['code']
    if not isinstance(code, str) or len(code) > 100_000:
        raise ValueError('Python 脚本超过 100 KB 或类型无效')
    log = Log()
    started = time.perf_counter()
    namespace = {'__name__': '__vision_script__'}
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        exec(compile(code, '<vision-script>', 'exec'), namespace)
        action = namespace.get('run')
        if not callable(action):
            raise ValueError('脚本必须定义 run(ctx) 函数')
        result = action(request['context'])
    if not isinstance(result, dict):
        raise ValueError('run(ctx) 必须返回字典')
    print(json.dumps({'ok': True, 'data': result, 'logs': log.text,
                      'elapsedMs': round((time.perf_counter()-started)*1000, 1)}, ensure_ascii=True, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        print(json.dumps({'ok': False, 'error': str(exc), 'trace': traceback.format_exc(limit=4)}, ensure_ascii=True))
