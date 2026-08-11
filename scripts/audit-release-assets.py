#!/usr/bin/env python3
"""Reject release assets or archive members that could expose private build inputs."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


CONTROL_ASSETS = {
    "ABIS.txt",
    "latest.json",
    "RELEASE-NOTES.md",
    "SHA256SUMS-android.txt",
    "SHA256SUMS-ios.txt",
    "SHA256SUMS-release.txt",
    "SHA256SUMS-unsigned.txt",
    "SIGNING.txt",
}
INSTALLER_SUFFIXES = (
    ".aab",
    ".apk",
    ".appimage",
    ".deb",
    ".dmg",
    ".exe",
    ".ipa",
    ".msi",
    ".rpm",
)
UPDATER_ARCHIVE_SUFFIXES = (
    ".app.tar.gz",
    ".appimage.tar.gz",
    ".msi.zip",
    ".nsis.zip",
)
CLI_ASSET_RE = re.compile(r"(?:^|[-_.])cli(?:[-_.]|$)", re.IGNORECASE)
SAFE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+_.() -]{0,239}\Z")
SENSITIVE_ASSET_MARKERS = (
    ".git",
    "private-src",
    "cargo.toml",
    "cargo.lock",
    "credentials",
    "private-key",
    "private_key",
    "secret",
    "source-map",
    "sourcemap",
    "token",
)
FORBIDDEN_MEMBER_PARTS = {
    ".git",
    ".idea",
    ".vscode",
    "private-src",
    "target",
}
FORBIDDEN_MEMBER_NAMES = {
    ".env",
    "cargo.lock",
    "cargo.toml",
    "credentials",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
}
FORBIDDEN_MEMBER_SUFFIXES = (
    ".dwo",
    ".dwp",
    ".map",
    ".pdb",
    ".rs",
)
RAW_SECRET_MARKERS = (
    b"PRIVATE_SOURCE_TOKEN",
    b"TAURI_SIGNING_PRIVATE_KEY",
    b"BEGIN OPENSSH PRIVATE KEY",
    b"private-src/",
    b"private-src\\",
)
RAW_TOKEN_RE = re.compile(rb"(?:gh[op]_|github_pat_)[A-Za-z0-9_]{20,}")
MAX_ARCHIVE_MEMBERS = 250_000


def fail(message: str) -> None:
    raise SystemExit(message)


def is_allowed_payload(name: str) -> bool:
    lowered = name.lower()
    if not (
        name.startswith("FanqieNovelDownloader")
        or name.startswith("Fanqie Downloader")
    ):
        return False
    if lowered.endswith(INSTALLER_SUFFIXES + UPDATER_ARCHIVE_SUFFIXES):
        return True
    if lowered.endswith(".zip"):
        return (
            "darwin-x64" in lowered
            or "darwin-aarch64" in lowered
            or CLI_ASSET_RE.search(name) is not None
        )
    if lowered.endswith((".tar.gz", ".tar.xz")):
        return CLI_ASSET_RE.search(name) is not None
    return False


def validate_asset_name(name: str) -> None:
    if not name or not SAFE_NAME_RE.fullmatch(name):
        fail(f"release asset has an unsafe name: {name!r}")
    lowered = name.lower()
    if any(marker in lowered for marker in SENSITIVE_ASSET_MARKERS):
        fail(f"release asset name contains a private/debug marker: {name}")
    if name in CONTROL_ASSETS:
        return
    if lowered.endswith(".sig"):
        payload = name[:-4]
        if not is_allowed_payload(payload):
            fail(f"release signature does not match an allowed payload name: {name}")
        return
    if not is_allowed_payload(name):
        fail(f"release asset is not on the publication allowlist: {name}")


def release_asset_names(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read release JSON {path}: {error}")
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list) or not assets:
        fail("release JSON does not contain any assets")
    names = []
    for asset in assets:
        if not isinstance(asset, dict):
            fail("release JSON contains a malformed asset")
        name = str(asset.get("name") or "").strip()
        validate_asset_name(name)
        names.append(name)
    if len(names) != len(set(names)):
        fail("release JSON contains duplicate asset names")
    return names


def normalize_member_name(value: str, archive: Path) -> PurePosixPath:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or normalized.startswith("/") or ".." in path.parts:
        fail(f"archive contains an unsafe member path: {archive.name}: {value!r}")
    if path.parts and re.fullmatch(r"[A-Za-z]:", path.parts[0]):
        fail(f"archive contains a host filesystem path: {archive.name}: {value!r}")
    return path


def validate_member_name(value: str, archive: Path) -> None:
    path = normalize_member_name(value, archive)
    parts = [part.lower() for part in path.parts]
    if any(part in FORBIDDEN_MEMBER_PARTS for part in parts):
        fail(f"archive contains a private/build directory: {archive.name}: {value}")
    if any(part.endswith(".dsym") for part in parts):
        fail(f"archive contains debug symbols: {archive.name}: {value}")
    basename = parts[-1] if parts else ""
    if basename in FORBIDDEN_MEMBER_NAMES:
        fail(f"archive contains a source/credential file: {archive.name}: {value}")
    if basename.endswith(FORBIDDEN_MEMBER_SUFFIXES):
        fail(f"archive contains source maps, source, or debug files: {archive.name}: {value}")
    if any(marker in basename for marker in ("private_key", "private-key", "access_token")):
        fail(f"archive contains a credential-like file: {archive.name}: {value}")


def scan_zip(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                fail(f"archive has too many members to audit safely: {path.name}")
            for member in members:
                validate_member_name(member.filename, path)
    except (OSError, zipfile.BadZipFile) as error:
        fail(f"cannot audit ZIP-compatible release asset {path}: {error}")


def scan_tar(path: Path) -> None:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            members = archive.getmembers()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                fail(f"archive has too many members to audit safely: {path.name}")
            for member in members:
                validate_member_name(member.name, path)
                if member.issym() or member.islnk():
                    normalize_member_name(member.linkname, path)
    except (OSError, tarfile.TarError) as error:
        fail(f"cannot audit TAR release asset {path}: {error}")


def scan_raw_markers(path: Path) -> None:
    lowered = path.name.lower()
    if lowered.endswith((".sig", ".txt", ".json")):
        return
    overlap = max(max(len(marker) for marker in RAW_SECRET_MARKERS), 96) - 1
    tail = b""
    try:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                sample = tail + chunk
                for marker in RAW_SECRET_MARKERS:
                    if marker in sample:
                        fail(
                            f"release asset contains a credential/private-path marker: "
                            f"{path.name}: {marker.decode('ascii', errors='replace')}"
                        )
                if RAW_TOKEN_RE.search(sample):
                    fail(f"release asset contains a GitHub token-like value: {path.name}")
                tail = sample[-overlap:] if overlap else b""
    except OSError as error:
        fail(f"cannot scan release asset {path}: {error}")


def audit_downloaded_assets(root: Path, expected_names: set[str]) -> int:
    if not root.is_dir():
        fail(f"downloaded release asset directory does not exist: {root}")
    entries = sorted(root.iterdir())
    if any(not path.is_file() for path in entries):
        fail("downloaded release directory contains nested directories or non-files")
    actual_names = {path.name for path in entries}
    if actual_names != expected_names:
        fail(
            "downloaded release assets do not match the GitHub asset list; "
            f"missing={sorted(expected_names - actual_names)}, "
            f"unexpected={sorted(actual_names - expected_names)}"
        )
    for path in entries:
        validate_asset_name(path.name)
        lowered = path.name.lower()
        if lowered.endswith((".zip", ".apk", ".aab", ".ipa")):
            scan_zip(path)
        elif lowered.endswith(".tar.gz"):
            scan_tar(path)
        scan_raw_markers(path)
    return len(entries)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-json", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    names = release_asset_names(args.release_json)
    if args.root is not None:
        count = audit_downloaded_assets(args.root, set(names))
        print(f"Release asset allowlist and archive audit passed: {count} files")
    else:
        print(f"Release asset allowlist passed: {len(names)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
