#!/usr/bin/env python3
"""按固定清单生成 Linux x86_64 用户级目录包；闭包共享库，不打包 glibc/真实设备 SDK。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def output(*args, **kwargs):
    """运行只读版本/依赖命令，非零立即失败，不伪造依赖完整。"""
    return subprocess.check_output(args, text=True, **kwargs).strip()


def copy(source, target):
    """复制实际文件并保留执行位，目录包内不允许指向开发前缀的符号链接。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target, follow_symlinks=True)


def dependencies(binary, env):
    """ldd 只用于本地可信构建产物；缺库立即失败。glibc/加载器保留宿主 ABI。"""
    text = output("ldd", str(binary), env=env)
    if "not found" in text:
        raise RuntimeError(text)
    return [Path(p) for p in re.findall(r"=> (/\S+)", text)
            if not re.match(r"lib(c|m|pthread|dl|rt|resolv|util)\.so", Path(p).name)]


def main():
    """收集可信发布输入、依赖版权与校验清单，按 Git 时间归一 tar 元数据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        parser.error("output exists; use a fresh directory (never overwrite a release)")
    qt = Path(os.environ.get("SIEANS_QT_PREFIX", str(Path.home()/"Qt/6.7.3/gcc_64")))
    ort = Path(os.environ.get("SIEANS_ONNXRUNTIME_DIR", str(Path.home()/".local/opt/onnxruntime")))
    tess = Path.home()/".local/opt/tesseract"
    cursor = Path.home()/".local/opt/xcb-cursor/usr/lib/x86_64-linux-gnu"
    revision = output("git", "rev-parse", "HEAD", cwd=ROOT)
    dirty = bool(output("git", "status", "--porcelain", cwd=ROOT))
    epoch = int(output("git", "show", "-s", "--format=%ct", "HEAD", cwd=ROOT))
    if target.with_suffix(".tar").exists():
        parser.error("archive exists; choose a fresh output")
    target.mkdir(parents=True)
    env = dict(os.environ, LD_LIBRARY_PATH=f"{qt}/lib:{ort}/lib:{cursor}:{tess}/usr/lib/x86_64-linux-gnu")
    try:
        copy(ROOT/"qtapp/build/sieans_qt", target/"qtapp/build/sieans_qt")
        copy(ROOT/"qtapp/resources/sample-qr.png", target/"qtapp/build/resources/sample-qr.png")
        copy(ROOT/"projects/open-and-run-gentl-qr.sieans", target/"projects/open-and-run-gentl-qr.sieans")
        # 仅选公开演示及 smoke stub，不收集用户模型/历史/现场工程。
        for name in ["sieans-yolo-smoke.onnx", "sieans-yolo-seg-smoke.onnx", "README.md"]:
            copy(ROOT/"models"/name, target/"models"/name)
        for script in (ROOT/"scripts/release").glob("*.sh"):
            copy(script, target/script.name)
        for group in ["platforms", "imageformats", "xcbglintegrations", "wayland-graphics-integration-client",
                      "wayland-decoration-client", "wayland-shell-integration", "tls"]:
            for plugin in (qt/"plugins"/group).glob("*.so"):
                copy(plugin, target/"plugins"/group/plugin.name)
        shutil.copytree(ort/"lib", target/"ort/lib", symlinks=False)
        for name in ["LICENSE", "ThirdPartyNotices.txt", "VERSION_NUMBER", "SIEANS-ONNXRUNTIME-ORIGIN.txt"]:
            copy(ort/name, target/"notices/onnxruntime"/name)
        shutil.copytree(tess/"usr", target/"tesseract/usr", symlinks=False)
        # 所有 ELF 的递归依赖闭包，含 Qt 插件与可选算法运行时。
        queue = [target/"qtapp/build/sieans_qt", target/"tesseract/usr/bin/tesseract"]
        queue += list((target/"plugins").rglob("*.so")) + list((target/"ort/lib").glob("*.so*"))
        visited = set()
        origins = {}
        while queue:
            binary = queue.pop()
            if binary.resolve() in visited:
                continue
            visited.add(binary.resolve())
            for dep in dependencies(binary, env):
                dest = target/"lib"/dep.name
                if not dest.exists():
                    copy(dep, dest)
                    origins[dep.name] = str(dep).replace(str(target), "$BUNDLE")
                    queue.append(dep)
        # 保留系统包版权与原生 ZXing 许可证；Qt 开源许可证在 notices 中随源码入口交付。
        for name, source in origins.items():
            probe = subprocess.run(["dpkg-query", "-S", source], text=True, capture_output=True)
            if probe.returncode == 0:
                package = probe.stdout.split(": ", 1)[0]
                notice = Path("/usr/share/doc")/package.split(":")[0]/"copyright"
                if notice.exists():
                    copy(notice, target/"notices/system"/(package.replace(":", "_")+".copyright"))
        for notice in (ROOT/"scripts/release/notices").glob("*"):
            copy(notice, target/"notices"/notice.name)
        for name in ["LICENSE", "COPYING", "NOTICE"]:
            for file in (ROOT/"native").glob(f"**/{name}*"):
                if "build" not in file.parts and file.is_file():
                    copy(file, target/"notices/native"/file.relative_to(ROOT/"native"))
        version = revision[:12] + ("-dirty" if dirty else "")
        (target/"VERSION").write_text(version+"\n")
        (target/"RELEASE.json").write_text(json.dumps({"commit": revision, "dirty": dirty,
            "sourceDateEpoch": epoch, "qt": "6.7.3", "host": output("getconf", "GNU_LIBC_VERSION"),
            "system": output("uname", "-sm"), "libraries": origins,
            "acceptance": "software only; no official model / GenTL / PLC certification"}, indent=2)+"\n")
        copy(ROOT/"docs/qt-release.md", target/"README.md")
        sums = []
        for file in sorted(target.rglob("*")):
            if file.is_file():
                sums.append(hashlib.sha256(file.read_bytes()).hexdigest()+"  "+str(file.relative_to(target)))
        (target/"SHA256SUMS").write_text("\n".join(sums)+"\n")
        # 固定 tar 顺序、uid/gid/mtime；相同输入生成相同 tar（不包含墙钟时间）。
        archive = target.with_suffix(".tar")
        if archive.exists():
            raise RuntimeError(f"archive exists: {archive}")
        with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as tar:
            for file in [target]+sorted(target.rglob("*")):
                info = tar.gettarinfo(str(file), arcname=str(Path("sieans-vision")/file.relative_to(target)))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = epoch
                info.pax_headers = {}
                if file.is_file():
                    with file.open("rb") as stream:
                        tar.addfile(info, stream)
                else:
                    tar.addfile(info)
        print(json.dumps({"directory": str(target), "archive": str(archive),
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "version": version}))
    except Exception:
        # 保留失败现场以便诊断；不生成成功标记，不自动覆盖/删除目录。
        raise


if __name__ == "__main__":
    main()
