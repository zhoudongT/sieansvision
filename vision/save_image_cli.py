#!/usr/bin/env python3
"""CLI helper: read data-URL JSON on stdin, write image in requested format."""
import argparse, base64, json, sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--format', default='png')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    req = json.load(sys.stdin)
    img = req.get('image') or ''
    raw = base64.b64decode(img.split(',', 1)[-1])
    try:
        import cv2, numpy as np
        arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
        if arr is None:
            raise ValueError('decode failed')
        fmt = args.format.lower().lstrip('.')
        ext = {'jpg': '.jpg', 'jpeg': '.jpg', 'png': '.png', 'bmp': '.bmp', 'tif': '.tif', 'tiff': '.tiff'}.get(fmt, '.' + fmt)
        out = args.out
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(out, arr)
        if not ok:
            raise SystemExit('imwrite failed')
        print(json.dumps({'ok': True, 'path': out, 'ext': ext}))
    except Exception as e:
        # fallback: write raw bytes
        Path(args.out).write_bytes(raw)
        print(json.dumps({'ok': True, 'path': args.out, 'fallback': str(e)}))

if __name__ == '__main__':
    main()
