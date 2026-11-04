#!/usr/bin/env python3
"""Package a macOS Tauri binary that was cross-compiled on Linux.

The Tauri bundler only builds .app/.dmg on a macOS host. When no macOS
runner is available, the release workflow compiles the binary on Linux
(cargo-zigbuild + macOS SDK) and this script produces the same layout the
native build ships:

  bundle/macos/<Product>.app            ad-hoc signed (ADHOC | RUNTIME)
  bundle/macos/<Product>.app.tar.gz     updater archive (signed later)
  bundle/dmg/<Product>_<version>_<arch>.dmg

It also checks the binary (Mach-O architecture, minimum macOS version,
linked libraries) and the signature before anything is uploaded.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tarfile
from pathlib import Path

CPU_TYPES = {
    "aarch64-apple-darwin": (0x0100000C, "aarch64"),
    "x86_64-apple-darwin": (0x01000007, "x64"),
}
MH_MAGIC_64 = 0xFEEDFACF
LC_LOAD_DYLIB = 0x0C
LC_LOAD_WEAK_DYLIB = 0x18 | 0x80000000
LC_REEXPORT_DYLIB = 0x1F | 0x80000000
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN_MACOSX = 0x24
LC_CODE_SIGNATURE = 0x1D
REQUIRED_LIBS = (
    "/System/Library/Frameworks/WebKit.framework/",
    "/System/Library/Frameworks/AppKit.framework/",
    "/System/Library/Frameworks/Foundation.framework/",
    "/usr/lib/libSystem.B.dylib",
)
SYSTEM_LIB_PREFIXES = ("/System/Library/", "/usr/lib/")


class BundleError(RuntimeError):
    pass


def inspect_macho(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 32:
        raise BundleError(f"{path} is too small to be a Mach-O binary")
    magic, cputype, _sub, filetype, ncmds, _size, _flags, _res = struct.unpack_from("<IiiIIIII", data, 0)
    if magic != MH_MAGIC_64:
        raise BundleError(f"{path} is not a 64-bit Mach-O binary (magic {magic:#x})")
    offset = 32
    libs: list[str] = []
    minos = None
    signed = False
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", data, offset)
        if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB):
            name_off = struct.unpack_from("<I", data, offset + 8)[0]
            raw = data[offset + name_off : offset + cmdsize]
            libs.append(raw.split(b"\0", 1)[0].decode())
        elif cmd == LC_BUILD_VERSION:
            _platform, raw_minos = struct.unpack_from("<II", data, offset + 8)
            minos = (raw_minos >> 16, (raw_minos >> 8) & 0xFF)
        elif cmd == LC_VERSION_MIN_MACOSX:
            raw_minos = struct.unpack_from("<I", data, offset + 8)[0]
            minos = (raw_minos >> 16, (raw_minos >> 8) & 0xFF)
        elif cmd == LC_CODE_SIGNATURE:
            signed = True
        offset += cmdsize
    return {"cputype": cputype & 0xFFFFFFFF, "filetype": filetype, "libs": libs, "minos": minos, "signed": signed}


def check_binary(path: Path, target: str, minimum_system_version: str) -> dict:
    expected_cpu, _arch = CPU_TYPES[target]
    info = inspect_macho(path)
    if info["cputype"] != expected_cpu:
        raise BundleError(f"{path.name}: CPU type {info['cputype']:#x}, expected {expected_cpu:#x} for {target}")
    if info["filetype"] != 2:
        raise BundleError(f"{path.name}: Mach-O file type {info['filetype']} is not an executable")
    if info["minos"] is None:
        raise BundleError(f"{path.name}: no minimum macOS version load command")
    wanted = tuple(int(part) for part in (minimum_system_version.split(".") + ["0"])[:2])
    floor = (11, 0) if target.startswith("aarch64") else wanted
    if info["minos"] > max(wanted, floor):
        raise BundleError(
            f"{path.name}: minimum macOS {info['minos'][0]}.{info['minos'][1]} is newer than {minimum_system_version}"
        )
    for required in REQUIRED_LIBS:
        if not any(lib.startswith(required) for lib in info["libs"]):
            raise BundleError(f"{path.name}: does not link {required}")
    stray = [lib for lib in info["libs"] if not lib.startswith(SYSTEM_LIB_PREFIXES)]
    if stray:
        raise BundleError(f"{path.name}: links libraries outside the system: {', '.join(stray)}")
    return info


def load_config(tauri_dir: Path, overrides: list[Path]) -> dict:
    def merge(base: dict, extra: dict) -> dict:
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                merge(base[key], value)
            else:
                base[key] = value
        return base

    config = json.loads((tauri_dir / "tauri.conf.json").read_text(encoding="utf-8"))
    for override in overrides:
        merge(config, json.loads(override.read_text(encoding="utf-8")))
    return config


def info_plist(config: dict, binary_name: str, version: str, minimum_system_version: str) -> dict:
    product = config["productName"]
    plist = {
        "CFBundleDevelopmentRegion": "English",
        "CFBundleDisplayName": product,
        "CFBundleExecutable": binary_name,
        "CFBundleIdentifier": config["identifier"],
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": product,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "CSResourcesFileMapped": True,
        "LSMinimumSystemVersion": minimum_system_version,
        "CFBundleIconFile": "icon.icns",
        "LSRequiresCarbon": True,
        "NSHighResolutionCapable": True,
    }
    copyright_text = config.get("bundle", {}).get("copyright")
    if copyright_text:
        plist["NSHumanReadableCopyright"] = copyright_text
    return plist


def resource_pairs(config: dict, tauri_dir: Path) -> list[tuple[Path, str]]:
    resources = config.get("bundle", {}).get("resources") or {}
    if isinstance(resources, list):
        pairs = [(tauri_dir / item, item) for item in resources]
    else:
        pairs = [(tauri_dir / src, dst) for src, dst in resources.items()]
    for src, _dst in pairs:
        if not src.is_file():
            raise BundleError(f"bundle resource {src} is missing (only plain files are supported here)")
    return pairs


def find_icns(config: dict, tauri_dir: Path) -> Path:
    for icon in config.get("bundle", {}).get("icon", []):
        if icon.endswith(".icns"):
            path = tauri_dir / icon
            if path.is_file():
                return path
    raise BundleError("no .icns icon in bundle.icon")


def build_app(config: dict, tauri_dir: Path, binary: Path, version: str, out_dir: Path) -> Path:
    product = config["productName"]
    minimum = config.get("bundle", {}).get("macOS", {}).get("minimumSystemVersion") or "10.13"
    app = out_dir / f"{product}.app"
    if app.exists():
        shutil.rmtree(app)
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump(info_plist(config, binary.name, version, minimum), handle, sort_keys=False)
    exe = contents / "MacOS" / binary.name
    shutil.copyfile(binary, exe)
    exe.chmod(0o755)
    shutil.copyfile(find_icns(config, tauri_dir), contents / "Resources" / "icon.icns")
    for src, dst in resource_pairs(config, tauri_dir):
        target = contents / "Resources" / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
    for path in app.rglob("*"):
        if path.is_dir():
            path.chmod(0o755)
        elif path != exe:
            path.chmod(0o644)
    app.chmod(0o755)
    return app


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise BundleError(f"{' '.join(cmd)} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
    return result.stdout


def sign_app(app: Path, rcodesign: str, identifier: str, binary_name: str) -> None:
    run([
        rcodesign, "sign",
        "--code-signature-flags", "runtime",
        "--binary-identifier", f"Contents/MacOS/{binary_name}:{identifier}",
        str(app),
    ])
    info = run([rcodesign, "print-signature-info", str(app / "Contents" / "MacOS" / binary_name)])
    if "ADHOC" not in info or "RUNTIME" not in info:
        raise BundleError(f"signature is not ad-hoc with hardened runtime:\n{info}")
    if not (app / "Contents" / "_CodeSignature" / "CodeResources").is_file():
        raise BundleError("bundle signature did not write _CodeSignature/CodeResources")


def make_updater_archive(app: Path) -> Path:
    archive = app.with_name(app.name + ".tar.gz")
    archive.unlink(missing_ok=True)

    def reset_owner(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(app, arcname=app.name, filter=reset_owner)
    return archive


def make_dmg(app: Path, dmg_path: Path, volume_name: str, tools: dict) -> Path:
    work = dmg_path.parent / f".{dmg_path.stem}-work"
    shutil.rmtree(work, ignore_errors=True)
    staging = work / "staging"
    staging.mkdir(parents=True)
    shutil.copytree(app, staging / app.name, symlinks=True)
    os.symlink("/Applications", staging / "Applications")
    payload = sum(p.stat().st_size for p in staging.rglob("*") if p.is_file() and not p.is_symlink())
    size_mb = max(16, int(payload * 1.3 / (1024 * 1024)) + 8)
    image = work / "image.hfs"
    with image.open("wb") as handle:
        handle.truncate(size_mb * 1024 * 1024)
    run([tools["mkfs"], "-v", volume_name, str(image)])
    run([tools["hfsplus"], str(image), "addall", str(staging), "--symlinks", "clone_link"])
    listing = run([tools["hfsplus"], str(image), "ls", "/" + app.name + "/Contents/MacOS"])
    if "100755" not in listing:
        raise BundleError(f"executable bit lost inside the DMG:\n{listing}")
    dmg_path.parent.mkdir(parents=True, exist_ok=True)
    dmg_path.unlink(missing_ok=True)
    run([tools["dmg"], "build", str(image), str(dmg_path)])
    shutil.rmtree(work, ignore_errors=True)
    return dmg_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tauri-dir", required=True, type=Path)
    parser.add_argument("--target", required=True, choices=sorted(CPU_TYPES))
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--config", action="append", default=[], type=Path, help="extra Tauri config merged on top")
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--rcodesign", default="rcodesign")
    parser.add_argument("--mkfs-hfsplus", default="mkfs.hfsplus")
    parser.add_argument("--hfsplus", default="hfsplus")
    parser.add_argument("--dmg", default="dmg")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.tauri_dir, args.config)
        minimum = config.get("bundle", {}).get("macOS", {}).get("minimumSystemVersion") or "10.13"
        info = check_binary(args.binary, args.target, minimum)
        _cpu, arch = CPU_TYPES[args.target]
        app = build_app(config, args.tauri_dir, args.binary, args.version, args.bundle_dir / "macos")
        sign_app(app, args.rcodesign, config["identifier"], args.binary.name)
        check_binary(app / "Contents" / "MacOS" / args.binary.name, args.target, minimum)
        archive = make_updater_archive(app)
        dmg = make_dmg(
            app,
            args.bundle_dir / "dmg" / f"{config['productName']}_{args.version}_{arch}.dmg",
            config["productName"],
            {"mkfs": args.mkfs_hfsplus, "hfsplus": args.hfsplus, "dmg": args.dmg},
        )
    except BundleError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    minos = info["minos"]
    print(f"macOS {args.target}: minimum {minos[0]}.{minos[1]}, {len(info['libs'])} system libraries")
    for path in (app, archive, dmg):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
