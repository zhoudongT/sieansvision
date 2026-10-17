import json
import os
import sys

# Keep native SDK diagnostics off the machine-readable response stream.
output = os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding='utf-8')
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
try:
    from adapter import run
    request = json.loads(sys.stdin.read(100_001))
    response = dict(ok=True, data=run(request))
except Exception as error:
    response = dict(ok=False, error=str(error)[:2000] or type(error).__name__)
output.write(json.dumps(response, ensure_ascii=False, allow_nan=False))
output.flush()
