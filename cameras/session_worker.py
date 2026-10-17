"""Persistent SDK connection, bounded line protocol and graceful stdin stop."""
import json
import os
import sys
import threading
import time

output = os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding='utf-8')
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
stopped = threading.Event()


def send(message):
    line = json.dumps(message, ensure_ascii=False, allow_nan=False)
    if len(line.encode('utf-8')) > 35_000_000:
        raise ValueError('相机帧超过 35 MB，请降低分辨率或增加点云采样步长')
    output.write(line+'\n')
    output.flush()  # Pipe backpressure prevents an unbounded output queue.


def watch_stop():
    # EOF, a stop command or invalid control input all stop acquisition.
    sys.stdin.readline(100)
    stopped.set()


def main():
    from adapter import config, capture_frames
    request = json.loads(sys.stdin.readline(110_001))
    p = config(request['params'])
    interval = request['intervalMs']/1000
    attempts = request['reconnectAttempts']
    reconnect = request['reconnectMs']/1000
    threading.Thread(target=watch_stop, daemon=True).start()
    retries = 0
    while not stopped.is_set():
        frames = capture_frames(p)
        try:
            while not stopped.is_set():
                started = time.monotonic()
                data = next(frames)
                if stopped.is_set():
                    break
                send(dict(event='frame', data=data))
                # Reconnect budget is per session, not reset by intermittent
                # successes; faulty devices cannot retry forever.
                stopped.wait(max(0, interval-(time.monotonic()-started)))
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
