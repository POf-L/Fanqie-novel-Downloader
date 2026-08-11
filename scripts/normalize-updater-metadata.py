#!/usr/bin/env python3
"""Build strict, package-specific Tauri updater metadata for a GitHub Release."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


SIGNATURE_FILE_RE = re.compile(r"(?:^|[\t ])file:([^\r\n]+)", re.MULTILINE)
CLI_ASSET_RE = re.compile(r"(?:^|[-_.])cli(?:[-_.]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class PackageSpec:
    platform: str
    asset_name: str
    package_kind: str
    architecture: str


PACKAGE_SPECS = (
    PackageSpec(
        "windows-x86_64-nsis",
        "FanqieNovelDownloader-tauri-windows-x64-setup.exe",
        "nsis",
        "x86_64",
    ),
    PackageSpec(
        "windows-x86_64-portable",
        "FanqieNovelDownloader-tauri-windows-x64-portable.exe",
        "portable",
        "x86_64",
    ),
    PackageSpec(
        "windows-aarch64-nsis",
        "FanqieNovelDownloader-tauri-windows-arm64-setup.exe",
        "nsis",
        "aarch64",
    ),
    PackageSpec(
        "windows-aarch64-portable",
        "FanqieNovelDownloader-tauri-windows-arm64-portable.exe",
        "portable",
        "aarch64",
    ),
    PackageSpec(
        "linux-x86_64-deb",
        "FanqieNovelDownloader-tauri-linux-amd64.deb",
        "deb",
        "x86_64",
    ),
    PackageSpec(
        "linux-x86_64-appimage",
        "FanqieNovelDownloader-tauri-linux-amd64.AppImage",
        "appimage",
        "x86_64",
    ),
    PackageSpec(
        "linux-aarch64-deb",
        "FanqieNovelDownloader-tauri-linux-arm64.deb",
        "deb",
        "aarch64",
    ),
    PackageSpec(
        "linux-aarch64-appimage",
        "FanqieNovelDownloader-tauri-linux-aarch64.AppImage",
        "appimage",
        "aarch64",
    ),
    PackageSpec(
        "darwin-x86_64-app",
        "FanqieNovelDownloader-tauri-darwin-x64.app.tar.gz",
        "app",
        "x86_64",
    ),
    PackageSpec(
        "darwin-aarch64-app",
        "FanqieNovelDownloader-tauri-darwin-aarch64.app.tar.gz",
        "app",
        "aarch64",
    ),
)
SPECS_BY_ASSET = {spec.asset_name: spec for spec in PACKAGE_SPECS}
PLATFORM_KEYS = {spec.platform for spec in PACKAGE_SPECS}


def release_version_for_tag(tag: str) -> str:
    value = tag.strip()
    unsigned = re.fullmatch(r"unsigned-v(.+)-r[1-9][0-9]*", value)
    if unsigned:
        return unsigned.group(1)
    return value.removeprefix("v")


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read JSON {path}: {error}") from error


def release_assets(payload: object) -> dict[str, dict]:
    assets = payload.get("assets") if isinstance(payload, dict) else payload
    if not isinstance(assets, list):
        raise SystemExit("release asset JSON must contain an assets array")

    by_name: dict[str, dict] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise SystemExit("release asset JSON contains a malformed asset")
        name = str(asset.get("name") or "").strip()
        if not name:
            raise SystemExit("release asset JSON contains an unnamed asset")
        if name in by_name:
            raise SystemExit(f"release contains duplicate asset name: {name}")
        by_name[name] = asset
    if not by_name:
        raise SystemExit("release asset JSON does not contain any named assets")
    return by_name


def expected_download_prefix(repo: str, tag: str) -> str:
    repo = repo.strip().strip("/")
    tag = tag.strip()
    if not re.fullmatch(r"[^/]+/[^/]+", repo):
        raise SystemExit(f"invalid GitHub repository: {repo!r}")
    if not tag or "/" in tag:
        raise SystemExit(f"invalid GitHub release tag: {tag!r}")
    return f"https://github.com/{repo}/releases/download/{quote(tag, safe='')}/"


def decoded_signature_filename(signature: str, signature_name: str) -> str:
    try:
        decoded = base64.b64decode(signature, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise SystemExit(f"invalid updater signature encoding: {signature_name}") from error
    match = SIGNATURE_FILE_RE.search(decoded)
    if match is None or not match.group(1).strip():
        raise SystemExit(f"updater signature has no signed filename: {signature_name}")
    return Path(match.group(1).strip()).name


def architecture_markers(architecture: str) -> tuple[str, ...]:
    if architecture == "aarch64":
        return ("arm64", "aarch64")
    return ("x64", "x86_64", "amd64")


def validate_signed_filename(spec: PackageSpec, signed_name: str) -> None:
    lowered = signed_name.lower()
    if spec.package_kind == "portable":
        if signed_name != spec.asset_name:
            raise SystemExit(
                "portable updater signature was not generated for the final asset name: "
                f"expected {spec.asset_name!r}, got {signed_name!r}"
            )
        return

    expected_suffix = {
        "nsis": "setup.exe",
        "deb": ".deb",
        "appimage": ".appimage",
        "app": ".app.tar.gz",
    }[spec.package_kind]
    if not lowered.endswith(expected_suffix):
        raise SystemExit(
            f"signature payload type does not match {spec.platform}: {signed_name!r}"
        )
    # Tauri's macOS updater archive uses the same internal filename for both
    # architectures. The release asset name and unique signature still bind the
    # entry to one architecture; Windows/Linux signatures also carry an arch marker.
    if spec.package_kind != "app" and not any(
        marker in lowered for marker in architecture_markers(spec.architecture)
    ):
        raise SystemExit(
            f"signature architecture does not match {spec.platform}: {signed_name!r}"
        )


def canonical_signature_file(item: Path) -> str:
    """Return the outer-base64 form consumed by Tauri updater metadata.

    `tauri signer sign` currently writes a one-line base64 encoding of the
    Minisign text. Keeping that value unchanged is important because it is
    also the value stored in `latest.json`. Some release tooling, however,
    provides the decoded four-line Minisign text instead. Accept that form
    too, and encode the original bytes once so both inputs produce the same
    metadata representation. Whitespace around or between base64 lines is
    harmless and is canonicalized.
    """
    try:
        raw = item.read_bytes()
    except OSError as error:
        raise SystemExit(f"cannot read updater signature {item}: {error}") from error
    if not raw.strip():
        raise SystemExit(f"updater signature is empty: {item.name}")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SystemExit(f"updater signature is not UTF-8 text: {item.name}") from error

    stripped = text.strip()
    if stripped.startswith("untrusted comment:"):
        return base64.b64encode(raw).decode("ascii")

    compact = re.sub(r"\s+", "", stripped)
    try:
        decoded = base64.b64decode(compact, validate=True)
        decoded.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise SystemExit(f"invalid updater signature encoding: {item.name}") from error
    return compact


def read_signatures(path: Path) -> dict[str, str]:
    if not path.is_dir():
        raise SystemExit(f"signature directory does not exist: {path}")
    signatures: dict[str, str] = {}
    for item in sorted(path.iterdir()):
        if not item.is_file():
            raise SystemExit(f"signature directory contains a non-file entry: {item.name}")
        if not item.name.lower().endswith(".sig"):
            raise SystemExit(f"signature directory contains an unexpected file: {item.name}")
        signatures[item.name] = canonical_signature_file(item)
    return signatures


def validate_windows_pairs(by_name: dict[str, dict]) -> None:
    for architecture in ("x64", "arm64"):
        required = {
            f"FanqieNovelDownloader-tauri-windows-{architecture}-setup.exe",
            f"FanqieNovelDownloader-tauri-windows-{architecture}-setup.exe.sig",
            f"FanqieNovelDownloader-tauri-windows-{architecture}-portable.exe",
            f"FanqieNovelDownloader-tauri-windows-{architecture}-portable.exe.sig",
        }
        present = required & by_name.keys()
        if present and present != required:
            missing = sorted(required - present)
            raise SystemExit(
                f"Windows {architecture} release shape is incomplete; missing: {missing}"
            )


def build_platforms(
    by_name: dict[str, dict], signatures: dict[str, str], prefix: str
) -> dict[str, dict[str, str]]:
    validate_windows_pairs(by_name)
    expected: dict[str, dict[str, str]] = {}
    used_signatures: dict[str, str] = {}

    for spec in PACKAGE_SPECS:
        signature_name = f"{spec.asset_name}.sig"
        has_payload = spec.asset_name in by_name
        has_signature_asset = signature_name in by_name
        if has_payload != has_signature_asset:
            missing = signature_name if has_payload else spec.asset_name
            raise SystemExit(
                f"updater payload/signature pair is incomplete for {spec.platform}: {missing}"
            )
        if not has_payload:
            continue
        signature = signatures.get(signature_name)
        if signature is None:
            raise SystemExit(f"downloaded signature file is missing: {signature_name}")
        signed_name = decoded_signature_filename(signature, signature_name)
        validate_signed_filename(spec, signed_name)
        duplicate = used_signatures.get(signature)
        if duplicate is not None:
            raise SystemExit(
                f"the same updater signature is reused by {duplicate} and {spec.platform}"
            )
        used_signatures[signature] = spec.platform
        expected[spec.platform] = {
            "signature": signature,
            "url": prefix + quote(spec.asset_name, safe=""),
        }

    known_signature_names = {f"{spec.asset_name}.sig" for spec in PACKAGE_SPECS}
    for name in by_name:
        if not name.lower().endswith(".sig") or name in known_signature_names:
            continue
        if not CLI_ASSET_RE.search(name):
            raise SystemExit(f"release contains an unsupported updater signature asset: {name}")
    extra_downloads = sorted(set(signatures) - set(by_name))
    if extra_downloads:
        raise SystemExit(
            "signature directory contains files not present in the Release: "
            + ", ".join(extra_downloads)
        )
    if not expected:
        raise SystemExit("release does not contain any supported updater package pairs")
    return expected


def normalize(
    metadata: dict,
    by_name: dict[str, dict],
    signatures: dict[str, str],
    prefix: str,
    release_version: str,
    *,
    check: bool,
) -> bool:
    actual_version = str(metadata.get("version") or "").strip()
    if actual_version != release_version:
        raise SystemExit(
            "latest.json version does not match the release tag: "
            f"expected {release_version!r}, got {actual_version!r}"
        )

    current = metadata.get("platforms")
    if not isinstance(current, dict) or not current:
        raise SystemExit("latest.json does not contain updater platforms")
    expected = build_platforms(by_name, signatures, prefix)
    if check:
        if current != expected:
            generic = sorted(key for key in current if key not in PLATFORM_KEYS)
            missing = sorted(expected.keys() - current.keys())
            unexpected = sorted(current.keys() - expected.keys())
            mismatched = sorted(
                key
                for key in expected.keys() & current.keys()
                if current[key] != expected[key]
            )
            raise SystemExit(
                "latest.json package entries are not strict and normalized; "
                f"generic_or_unknown={generic}, missing={missing}, "
                f"unexpected={unexpected}, mismatched={mismatched}"
            )
        return False
    if current == expected:
        return False
    metadata["platforms"] = expected
    return True


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--signatures-dir", type=Path, required=True)
    parser.add_argument("--repo", required=True, help="OWNER/REPOSITORY")
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless metadata contains only exact package-specific entries",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata = read_json(args.metadata)
    if not isinstance(metadata, dict):
        raise SystemExit("latest.json must contain a JSON object")
    assets_payload = read_json(args.assets)
    by_name = release_assets(assets_payload)
    signatures = read_signatures(args.signatures_dir)
    prefix = expected_download_prefix(args.repo, args.tag)
    changed = normalize(
        metadata,
        by_name,
        signatures,
        prefix,
        release_version_for_tag(args.tag),
        check=args.check,
    )
    if not args.check and changed:
        write_json(args.metadata, metadata)
    print(
        f"Updater metadata {'verified' if args.check else 'normalized'}: "
        f"{len(metadata['platforms'])} package-specific entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
