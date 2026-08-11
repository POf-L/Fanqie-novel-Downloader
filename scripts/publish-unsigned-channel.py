#!/usr/bin/env python3
"""Publish the latest unsigned updater metadata through a fixed unsigned alias."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


METADATA_NAME = "latest.json"
DEFAULT_ALIAS_TAG = "unsigned"
UNSIGNED_TAG_RE = re.compile(r"^unsigned-v[^/]+-r[1-9][0-9]*$")
STRICT_PACKAGE_KEYS = {
    "windows-x86_64-nsis",
    "windows-x86_64-portable",
    "windows-aarch64-nsis",
    "windows-aarch64-portable",
    "linux-x86_64-deb",
    "linux-x86_64-appimage",
    "linux-aarch64-deb",
    "linux-aarch64-appimage",
    "darwin-x86_64-app",
    "darwin-aarch64-app",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def run(command: list[str], *, capture: bool = False, input_text: str | None = None) -> str:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        check=True,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if result.stdout is not None else ""


def gh_json(arguments: list[str], *, input_text: str | None = None) -> object:
    try:
        return json.loads(run(["gh", *arguments], capture=True, input_text=input_text))
    except json.JSONDecodeError as error:
        fail(f"GitHub CLI returned invalid JSON: {error}")


def list_releases(repo: str) -> list[dict]:
    payload = gh_json(
        ["api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100"]
    )
    if not isinstance(payload, list):
        fail("GitHub release list is malformed")
    return [
        item
        for page in payload
        if isinstance(page, list)
        for item in page
        if isinstance(item, dict)
    ]


def names(release: dict) -> set[str]:
    return {
        str(asset.get("name") or "")
        for asset in release.get("assets", [])
        if isinstance(asset, dict)
    }


def has_updater(release: dict) -> bool:
    values = {name.lower() for name in names(release)}
    return METADATA_NAME in values and any(name.endswith(".sig") for name in values)


def select_source(releases: list[dict], requested: str = "") -> dict:
    requested = requested.strip()
    candidates = (
        [item for item in releases if item.get("tag_name") == requested]
        if requested
        else [
            item
            for item in releases
            if UNSIGNED_TAG_RE.fullmatch(str(item.get("tag_name") or ""))
        ]
    )
    candidates = [
        item
        for item in candidates
        if item.get("draft") is False
        and item.get("prerelease") is False
        and has_updater(item)
    ]
    candidates.sort(
        key=lambda item: (str(item.get("published_at") or ""), int(item.get("id") or 0)),
        reverse=True,
    )
    if not candidates:
        fail("no published unsigned release with updater metadata is available")
    return candidates[0]


def release_by_tag(repo: str, tag: str) -> dict | None:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/releases/tags/{quote(tag, safe='')}"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        fail(f"GitHub release API returned invalid JSON: {error}")
    return value if isinstance(value, dict) else None


def validate_metadata(repo: str, source: dict, metadata: dict) -> None:
    source_tag = str(source.get("tag_name") or "")
    source_assets = {
        str(asset.get("name") or ""): asset
        for asset in source.get("assets", [])
        if isinstance(asset, dict)
    }
    platforms = metadata.get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        fail("unsigned updater metadata has no platform entries")
    unsupported = sorted(set(platforms) - STRICT_PACKAGE_KEYS)
    if unsupported:
        fail(
            "unsigned metadata contains generic or unsupported package keys: "
            + ", ".join(unsupported)
        )
    prefix = f"https://github.com/{repo}/releases/download/{quote(source_tag, safe='')}/"
    for platform, entry in platforms.items():
        if not isinstance(entry, dict) or not str(entry.get("signature") or "").strip():
            fail(f"unsigned updater entry has no signature: {platform}")
        url = str(entry.get("url") or "").strip()
        if not url.startswith(prefix):
            fail(f"unsigned updater URL does not point to {source_tag}: {platform}")
        asset_name = unquote(url[len(prefix) :].split("?", 1)[0])
        asset = source_assets.get(asset_name)
        if asset is None or asset_name == METADATA_NAME or asset_name.lower().endswith(".sig"):
            fail(f"unsigned updater URL names an invalid source asset: {platform}")
        expected_shape = {
            "-nsis": ("windows-", "setup.exe"),
            "-portable": ("windows-", "portable.exe"),
            "-deb": ("linux-", ".deb"),
            "-appimage": ("linux-", ".appimage"),
            "-app": ("darwin-", ".app.tar.gz"),
        }
        _, (platform_marker, asset_suffix) = next(
            (suffix, shape)
            for suffix, shape in expected_shape.items()
            if platform.endswith(suffix)
        )
        lowered_name = asset_name.lower()
        if platform_marker not in lowered_name or not lowered_name.endswith(asset_suffix):
            fail(
                f"unsigned metadata package key does not match its asset: {platform} -> {asset_name}"
            )
        if "aarch64" in platform:
            architecture_matches = "arm64" in lowered_name or "aarch64" in lowered_name
        else:
            architecture_matches = any(
                marker in lowered_name for marker in ("x64", "amd64")
            )
        if not architecture_matches:
            fail(f"unsigned metadata architecture does not match its asset: {platform}")
        browser = str(asset.get("browser_download_url") or "")
        if urlsplit(browser).path != urlsplit(url).path:
            fail(f"unsigned updater URL does not match source asset: {platform}")


def download_metadata(repo: str, tag: str, directory: Path) -> tuple[Path, dict]:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / METADATA_NAME
    run(
        [
            "gh",
            "release",
            "download",
            tag,
            "--repo",
            repo,
            "--pattern",
            METADATA_NAME,
            "--dir",
            str(directory),
            "--clobber",
        ]
    )
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read unsigned updater metadata: {error}")
    if not isinstance(metadata, dict):
        fail("unsigned updater metadata must be a JSON object")
    return path, metadata


def upsert_alias(repo: str, alias_tag: str, source: dict) -> dict:
    source_tag = str(source.get("tag_name") or "")
    target = str(source.get("target_commitish") or "").strip()
    if not target:
        fail("unsigned source release has no target commit")
    body = "\n".join(
        [
            "这是无签名构建的自动更新通道元数据别名，不提供独立安装包。",
            "",
            f"- 无签名源 Release：`{source_tag}`",
            f"- 元数据下载：[latest.json](https://github.com/{repo}/releases/download/{quote(source_tag, safe='')}/latest.json)",
            "- 此通道只跟随正式无签名 Release；测试 prerelease 不会进入该通道。",
            "- 此通道只供明确安装无签名构建的客户端使用；普通签名版仍使用 `stable`。",
        ]
    )
    payload = {
        "tag_name": alias_tag,
        "target_commitish": target,
        "name": "番茄小说下载器无签名更新通道",
        "body": body,
        "draft": False,
        "prerelease": True,
        "make_latest": "false",
    }
    existing = release_by_tag(repo, alias_tag)
    if existing is None:
        return gh_json(
            ["api", "--method", "POST", f"repos/{repo}/releases", "--input", "-"],
            input_text=json.dumps(payload, ensure_ascii=False),
        )
    database_id = existing.get("id")
    if not isinstance(database_id, int):
        fail("unsigned alias has no numeric release ID")
    return gh_json(
        [
            "api",
            "--method",
            "PATCH",
            f"repos/{repo}/releases/{database_id}",
            "--input",
            "-",
        ],
        input_text=json.dumps(
            {
                key: payload[key]
                for key in ("name", "body", "draft", "prerelease", "make_latest")
            },
            ensure_ascii=False,
        ),
    )


def remove_extra_assets(repo: str, alias: dict) -> None:
    for asset in alias.get("assets", []):
        if not isinstance(asset, dict) or asset.get("name") == METADATA_NAME:
            continue
        asset_id = asset.get("id")
        if not isinstance(asset_id, int):
            fail("unsigned alias contains an asset without an ID")
        run(["gh", "api", "--method", "DELETE", f"repos/{repo}/releases/assets/{asset_id}"])


def verify_public(repo: str, alias_tag: str, expected: dict, source_tag: str) -> None:
    url = f"https://github.com/{repo}/releases/download/{quote(alias_tag, safe='')}/{METADATA_NAME}"
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                if getattr(response, "status", 200) != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                actual = json.loads(response.read().decode("utf-8"))
            if actual != expected:
                raise RuntimeError("endpoint returned different metadata")
            for entry in actual.get("platforms", {}).values():
                if f"/download/{quote(source_tag, safe='')}/" not in str(entry.get("url") or ""):
                    raise RuntimeError("endpoint rewrote the source tag")
            return
        except Exception as error:  # noqa: BLE001 - bounded public endpoint retry
            if attempt == 5:
                fail(f"unsigned metadata endpoint verification failed: {error}")
            time.sleep(2)


def refresh_unsigned_channel(
    *, repo: str, source_tag: str = "", alias_tag: str = DEFAULT_ALIAS_TAG, work_dir: Path
) -> str:
    if not os.environ.get("GH_TOKEN"):
        fail("GH_TOKEN is required")
    source = select_source(list_releases(repo), source_tag)
    source_tag = str(source.get("tag_name") or "")
    metadata_path, metadata = download_metadata(repo, source_tag, work_dir)
    validate_metadata(repo, source, metadata)
    alias = upsert_alias(repo, alias_tag, source)
    remove_extra_assets(repo, alias)
    run(["gh", "release", "upload", alias_tag, str(metadata_path), "--repo", repo, "--clobber"])
    alias = release_by_tag(repo, alias_tag)
    if alias is None or alias.get("draft") is not False or alias.get("prerelease") is not True:
        fail("unsigned alias is not a published prerelease")
    if names(alias) != {METADATA_NAME}:
        fail(f"unsigned alias must contain only latest.json, got {sorted(names(alias))!r}")
    verify_public(repo, alias_tag, metadata, source_tag)
    print(f"Unsigned channel refreshed: {alias_tag} -> {source_tag}", flush=True)
    return source_tag


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-tag", default="")
    parser.add_argument("--alias-tag", default=DEFAULT_ALIAS_TAG)
    parser.add_argument("--work-dir", type=Path, default=Path("unsigned-channel-check"))
    args = parser.parse_args()
    refresh_unsigned_channel(
        repo=args.repo,
        source_tag=args.source_tag,
        alias_tag=args.alias_tag,
        work_dir=args.work_dir.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
