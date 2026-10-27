#!/usr/bin/env python3
"""Download Bilibili multipage parts + extract keyframes via OpenCV (no yt-dlp/ffmpeg)."""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import cv2

BVID = "BV19vUfBVEpp"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER = f"https://www.bilibili.com/video/{BVID}/"


def http_json(url: str, *, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": REFERER},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_download(url: str, dest: Path, *, timeout: int = 60) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": REFERER,
            "Origin": "https://www.bilibili.com",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total and done % (1024 * 1024) < 256 * 1024:
                print(f"  {done/1e6:.1f}/{total/1e6:.1f} MB", flush=True)
    tmp.replace(dest)


def list_pages() -> list[dict]:
    data = http_json(f"https://api.bilibili.com/x/web-interface/view?bvid={BVID}")
    if data.get("code") != 0:
        raise RuntimeError(f"view API: {data}")
    return data["data"]["pages"]


def play_url(cid: int, qn: int = 64) -> str:
    # fnval=1 = MP4 single stream when available; fall back dash
    for fnval in (1, 16, 0):
        url = (
            "https://api.bilibili.com/x/player/playurl?"
            + urllib.parse.urlencode(
                {"bvid": BVID, "cid": cid, "qn": qn, "fnval": fnval, "fourk": 0}
            )
        )
        data = http_json(url)
        if data.get("code") != 0:
            print(f"  playurl code={data.get('code')} fnval={fnval}: {data.get('message')}", flush=True)
            continue
        d = data.get("data") or {}
        durls = d.get("durl") or []
        if durls:
            return durls[0]["url"]
        dash = d.get("dash") or {}
        videos = dash.get("video") or []
        if videos:
            # prefer AVC
            videos = sorted(videos, key=lambda v: (-int(v.get("id") or 0), 0 if "avc" in (v.get("codecs") or "") else 1))
            return videos[0].get("baseUrl") or videos[0].get("base_url")
    raise RuntimeError(f"no play url for cid={cid}")


def safe_name(part: str, page: int) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", part).strip("_")
    return f"p{page:02d}_{cleaned[:60]}"


def extract_frames(video: Path, out_dir: Path, every_sec: float = 10.0) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        print(f"  WARN cannot open {video}", flush=True)
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(fps * every_sec))
    idx = 0
    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            # shrink wide frames for notes
            h, w = frame.shape[:2]
            if w > 1280:
                scale = 1280 / w
                frame = cv2.resize(frame, (1280, int(h * scale)))
            ts = idx / fps
            name = out_dir / f"frame_{saved:03d}_t{int(ts):04d}s.jpg"
            cv2.imwrite(str(name), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            saved += 1
        idx += 1
    cap.release()
    return saved


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    videos = root / "videos"
    frames = root / "frames"
    pages = {int(p["page"]): p for p in list_pages()}
    want = [int(x) for x in argv] if argv else sorted(pages)
    for page in want:
        info = pages[page]
        cid = int(info["cid"])
        base = safe_name(info["part"], page)
        dest = videos / f"{base}.mp4"
        print(f"== p={page} {info['part']} cid={cid}", flush=True)
        if dest.exists() and dest.stat().st_size > 50_000:
            print(f"  skip download ({dest.stat().st_size} bytes)", flush=True)
        else:
            for attempt in range(3):
                try:
                    url = play_url(cid)
                    print(f"  url ok attempt={attempt+1}", flush=True)
                    http_download(url, dest)
                    break
                except Exception as exc:
                    print(f"  download fail: {exc}", flush=True)
                    time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  FAILED p={page}", flush=True)
                continue
        out = frames / base
        n = extract_frames(dest, out, every_sec=10.0)
        print(f"  frames={n} -> {out}", flush=True)
        # sidecar meta
        (out / "meta.json").write_text(
            json.dumps({"page": page, "part": info["part"], "cid": cid, "frames": n, "video": str(dest)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
