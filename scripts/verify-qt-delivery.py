#!/usr/bin/env python3
"""有界、隔离的 Qt 交付回归；不停止其它实例，不接现场设备。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import socket
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TESTS = "PIN_GROUP PROTOCOL_ROBUST YOLO PROJECT SCHEME SUBFLOW SOCKET SERIAL MODBUS S7 OPCUA MQTT MEASURE GEOMETRY LOCATE DEFECTS CONDITION EXPR FLOWEXTRAS IO_RESOLVE".split()


def process_sample(pid):
    """Linux /proc 实测 RSS/FD；进程退出竞态返回 None，不把缺测写成0。"""
    try:
        text = Path(f"/proc/{pid}/status").read_text()
        rss = re.search(r"VmRSS:\s+(\d+)", text)
        if not rss:
            return None
        return {"rssKiB": int(rss.group(1)), "fds": len(list(Path(f"/proc/{pid}/fd").iterdir()))}
    except (FileNotFoundError, ProcessLookupError):
        return None


def owned_loopback_ports(pid):
    """只读取本次 PID 的监听 socket；不扫描/停止用户其它实例。"""
    try:
        inodes = {os.readlink(p)[8:-1] for p in Path(f"/proc/{pid}/fd").iterdir()
                  if os.readlink(p).startswith("socket:[")}
        ports = set()
        for row in Path("/proc/net/tcp").read_text().splitlines()[1:]:
            fields = row.split()
            address, port = fields[1].split(":")
            if fields[3] == "0A" and fields[9] in inodes and address == "0100007F":
                ports.add(int(port, 16))
        return ports
    except (FileNotFoundError, ProcessLookupError):
        return set()


def run_case(launcher, directory, flags, timeout=330):
    """监督仅本次子进程；硬超时 terminate/kill，自测输出和 RSS 趋势全部留档。"""
    directory.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("SIEANS_QT_")}
    qt = Path(os.environ.get("SIEANS_QT_PREFIX", str(Path.home()/"Qt/6.7.3/gcc_64")))
    env.update({"QT_QPA_PLATFORM": "offscreen", "QT_PLUGIN_PATH": str(qt/"plugins"),
        "LD_LIBRARY_PATH": f"{qt}/lib:{Path.home()}/.local/opt/onnxruntime/lib",
        "SIEANS_QT_HEADLESS": "1", "SIEANS_QT_USER_DATA": str(directory/"data"),
        "SIEANS_QT_LOG_DIR": str(directory/"logs"), "SIEANS_QT_ARTIFACTS": str(directory/"artifacts"),
        "XDG_CONFIG_HOME": str(directory/"config"), "XDG_DATA_HOME": str(directory/"xdg-data"),
        "SIEANS_QT_RECENT_PATH": str(directory/"recent.ini"), **flags})
    samples = []
    owned_ports = set()
    timed_out = False
    start = time.monotonic()
    with (directory/"console.txt").open("w") as console:
        process = subprocess.Popen([str(launcher)], env=env, cwd=directory, stdout=console, stderr=subprocess.STDOUT)
        while process.poll() is None:
            owned_ports.update(owned_loopback_ports(process.pid))
            sample = process_sample(process.pid)
            if sample:
                samples.append({"elapsedS": round(time.monotonic()-start, 2), **sample})
            if time.monotonic()-start > timeout:
                timed_out = True
                process.terminate()
                try:
                    process.wait(5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                break
            time.sleep(0.2)
    logs = "\n".join(p.read_text(errors="replace") for p in (directory/"logs").glob("*.log*"))
    stdout = (directory/"console.txt").read_text(errors="replace")
    (directory/"samples.json").write_text(json.dumps(samples, indent=2))
    # 预热前半段不参与末段趋势；短时趋势只作本次预算判定，不是无泄漏证明。
    warm = samples[len(samples)//2:]
    growth = warm[-1]["rssKiB"]-warm[0]["rssKiB"] if warm else None
    released_ports = []
    for port in sorted(owned_ports):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", port))
            released_ports.append(port)
    result = {"releasedLoopbackPorts": released_ports, "exitCode": process.returncode, "timeout": timed_out,
        "elapsedS": round(time.monotonic()-start, 2), "peakRssKiB": max((s["rssKiB"] for s in samples), default=None),
        "secondHalfGrowthKiB": growth, "peakFds": max((s["fds"] for s in samples), default=None),
        "cleanExit": "session-clean-exit" in logs, "evidence": str(directory)}
    if process.returncode != 0 or timed_out:
        raise AssertionError(result)
    return result, stdout, logs


def main():
    """依次回归既有20自测，再用独立端口自选环回实例跑 smoke/soak/并发退出。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=40)
    parser.add_argument("--launcher", type=Path, default=ROOT/"scripts/run-sieans-qt.sh")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 2 <= args.cycles <= 1000:
        parser.error("cycles must be 2..1000")
    directory = args.output or Path(tempfile.mkdtemp(prefix="qt-delivery-", dir=ROOT/"artifacts"))
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report = {"hardware": "software-loopback only; no /dev/video* nodes" if not list(Path('/dev').glob('video*')) else "UVC nodes exist; manual capture verification required", "selftests": {}}
    launcher = args.launcher.resolve()
    for name in TESTS:
        result, stdout, _ = run_case(launcher, directory/name,
            {f"SIEANS_QT_{name}_SELFTEST": "1", f"SIEANS_QT_{name}_SELFTEST_QUIT": "1",
             "SIEANS_QT_REQUIRE_ONNX_SELFTEST": "1"})
        assert "-selftest ok" in stdout, (name, stdout)
        report["selftests"][name] = result
        print("PASS", name, flush=True)
    seed = {"SIEANS_QT_FORCE_SEED": "1", "SIEANS_QT_AUTO_SOFT": "1"}
    result, _, logs = run_case(launcher, directory/"smoke", {**seed, "SIEANS_QT_AUTO_RUN": "1",
        "SIEANS_QT_AUTO_TCP": "1", "SIEANS_QT_SCREENSHOT": str(directory/"smoke.png"),
        "SIEANS_QT_SCREENSHOT_QUIT": "1", "SIEANS_QT_SMOKE_REPORT": str(directory/"smoke.txt")})
    smoke = (directory/"smoke.txt").read_text()
    for expected in ["codes=2", "passGate=1", "urlOk=1", "ocrAvail=1", "ocrOk=1", "projectDirty=0",
                     "yoloBackend=software", "yoloSegBackend=software"]:
        assert expected in smoke, expected
    assert result["cleanExit"], result
    report["smoke"] = result
    print("PASS smoke", flush=True)
    result, _, logs = run_case(launcher, directory/"soak", {**seed, "SIEANS_QT_SOAK_CYCLES": str(args.cycles), "SIEANS_QT_LOG_MAX_BYTES": "16384"})
    assert f"soak-complete cycles= {args.cycles}" in logs, logs[-2000:]
    assert result["cleanExit"], result
    assert result["secondHalfGrowthKiB"] is not None and result["secondHalfGrowthKiB"] < 65536, result
    p95 = re.search(r"p95Ms=\s+([\d.]+)", logs)
    result["p95SoftwareMs"] = float(p95.group(1)) if p95 else None
    result["cycles"] = args.cycles
    log_files = list((directory/"soak/logs").glob("session-*.log*"))
    assert 1 <= len(log_files) <= 3 and all(p.stat().st_size <= 16384 for p in log_files)
    result["rotatedLogFiles"] = len(log_files)
    report["soak"] = result
    print("PASS soak", json.dumps(result), flush=True)
    # 多实例同时运行：程序自己只在loopback可用端口范围内选取，不操作用户旧进程。
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_case, launcher, directory/f"parallel-{i}",
            {**seed, "SIEANS_QT_SOAK_CYCLES": "4"}) for i in range(2)]
        report["parallel"] = [f.result()[0] for f in futures]
    assert all(r["cleanExit"] for r in report["parallel"])
    report["conclusion"] = "bounded regression passed; RSS trend budget <64MiB in second half; NOT proof of no leaks or field acceptance"
    (directory/"report.json").write_text(json.dumps(report, indent=2)+"\n")
    print("PASS delivery", directory, flush=True)


if __name__ == "__main__":
    main()
