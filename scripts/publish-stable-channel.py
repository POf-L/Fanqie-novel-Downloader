#!/usr/bin/env python3
"""Publish the signed updater metadata through a fixed ``stable`` alias."""

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
DEFAULT_ALIAS_TAG = "stable"
SIGNED_TAG_RE = re.compile(r"^v[^/]+$")


def fail(message: str) -> None:
    raise SystemExit(message)


def run(
    command: list[str],
    *,
    capture: bool = False,
    input_text: str | None = None,
) -> str:
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
    output = run(["gh", *arguments], capture=True, input_text=input_text)
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        fail(f"GitHub CLI returned invalid JSON: {error}")


def validate_repo(repo: str) -> str:
    value = repo.strip().strip("/")
    if not re.fullmatch(r"[^/]+/[^/]+", value):
        fail(f"invalid GitHub repository: {repo!r}")
    return value


def list_releases(repo: str) -> list[dict]:
    payload = gh_json(
        [
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repo}/releases?per_page=100",
        ]
    )
    if not isinstance(payload, list):
        fail("GitHub release list returned an unexpected payload")
    releases: list[dict] = []
    for page in payload:
        if not isinstance(page, list):
            fail("GitHub release list page is malformed")
        releases.extend(item for item in page if isinstance(item, dict))
    return releases


def asset_names(release: dict) -> set[str]:
    return {
        str(asset.get("name") or "")
        for asset in release.get("assets", [])
        if isinstance(asset, dict)
    }


def asset_records(release: dict) -> dict[str, dict]:
    return {
        str(asset.get("name") or ""): asset
        for asset in release.get("assets", [])
        if isinstance(asset, dict) and str(asset.get("name") or "")
    }


def is_signed_release(release: dict) -> bool:
    tag = str(release.get("tag_name") or "")
    names = asset_names(release)
    return (
        bool(tag and SIGNED_TAG_RE.fullmatch(tag))
        and release.get("draft") is False
        and release.get("prerelease") is False
        and METADATA_NAME in names
        and any(name.lower().endswith(".sig") for name in names)
    )


def select_signed_release(
    releases: list[dict], requested_tag: str = ""
) -> dict:
    requested = requested_tag.strip()
    if requested:
        matches = [
            release
            for release in releases
            if release.get("tag_name") == requested
        ]
        if len(matches) != 1:
            fail(f"signed source release not found: {requested!r}")
        if not is_signed_release(matches[0]):
            fail(f"source release is not a published signed release: {requested!r}")
        return matches[0]

    candidates = [release for release in releases if is_signed_release(release)]
    candidates.sort(
        key=lambda release: (
            str(release.get("published_at") or ""),
            int(release.get("id") or 0),
        ),
        reverse=True,
    )
    if not candidates:
        fail("no published signed release with updater metadata is available")
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
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        fail(f"GitHub release API returned invalid JSON for {tag!r}: {error}")
    return payload if isinstance(payload, dict) else None


def source_metadata_url(repo: str, source_tag: str) -> str:
    return (
        f"https://github.com/{repo}/releases/download/"
        f"{quote(source_tag, safe='')}/{METADATA_NAME}"
    )


def validate_metadata(
    metadata: dict,
    *,
    repo: str,
    source_tag: str,
    source_release: dict,
) -> None:
    expected_version = source_tag.removeprefix("v")
    if str(metadata.get("version") or "").strip() != expected_version:
        fail(
            "stable metadata version does not match source release: "
            f"expected {expected_version!r}, got {metadata.get('version')!r}"
        )
    platforms = metadata.get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        fail("stable metadata does not contain updater platforms")
    source_assets = asset_records(source_release)
    expected_prefix = (
        f"https://github.com/{repo}/releases/download/"
        f"{quote(source_tag, safe='')}/"
    )
    for platform, entry in platforms.items():
        if not isinstance(entry, dict):
            fail(f"stable metadata entry is malformed: {platform}")
        if not str(entry.get("signature") or "").strip():
            fail(f"stable metadata entry has no signature: {platform}")
        url = str(entry.get("url") or "").strip()
        if not url.startswith(expected_prefix):
            fail(f"stable metadata URL does not point to {source_tag}: {platform}")
        name = unquote(url.removeprefix(expected_prefix).split("?", 1)[0])
        source_asset = source_assets.get(name)
        if not name or source_asset is None:
            fail(f"stable metadata URL names an unknown source asset: {platform}")
        browser_download_url = str(source_asset.get("browser_download_url") or "").strip()
        if not browser_download_url:
            fail(f"source release asset has no download URL: {platform}")
        metadata_url = urlsplit(url)
        source_url = urlsplit(browser_download_url)
        if (
            metadata_url.scheme.lower() != "https"
            or metadata_url.netloc.lower() != "github.com"
            or source_url.scheme.lower() != "https"
            or source_url.netloc.lower() != "github.com"
            or unquote(metadata_url.path) != unquote(source_url.path)
        ):
            fail(f"stable metadata URL does not match the source asset: {platform}")


def download_source_metadata(
    *,
    repo: str,
    source_tag: str,
    work_dir: Path,
) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = work_dir / METADATA_NAME
    run(
        [
            "gh",
            "release",
            "download",
            source_tag,
            "--repo",
            repo,
            "--pattern",
            METADATA_NAME,
            "--dir",
            str(work_dir),
            "--clobber",
        ]
    )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read downloaded stable metadata: {error}")
    if not isinstance(metadata, dict):
        fail("stable metadata must be a JSON object")
    return metadata


def upsert_alias(
    *,
    repo: str,
    alias_tag: str,
    source_release: dict,
) -> dict:
    source_tag = str(source_release.get("tag_name") or "")
    title = "番茄小说下载器稳定更新通道"
    body = "\n".join(
        [
            "这是稳定自动更新通道的元数据别名，不提供独立安装包。",
            "",
            f"- 稳定源 Release：`{source_tag}`",
            f"- 元数据下载：[latest.json]({source_metadata_url(repo, source_tag)})",
            "- 手动下载请使用 GitHub Releases 页面上的正式版本。",
        ]
    )
    existing = release_by_tag(repo, alias_tag)
    payload = json.dumps(
        {
            "tag_name": alias_tag,
            "target_commitish": source_tag,
            "name": title,
            "body": body,
            "draft": False,
            "prerelease": True,
            "make_latest": False,
        },
        ensure_ascii=False,
    )
    if existing is None:
        alias = gh_json(
            [
                "api",
                "--method",
                "POST",
                f"repos/{repo}/releases",
                "--input",
                "-",
            ],
            input_text=payload,
        )
    else:
        if existing.get("tag_name") != alias_tag:
            fail(f"stable alias tag mismatch: {existing.get('tag_name')!r}")
        database_id = existing.get("id")
        if not isinstance(database_id, int):
            fail("stable alias has no numeric release ID")
        alias = gh_json(
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
                    "name": title,
                    "body": body,
                    "draft": False,
                    "prerelease": True,
                    "make_latest": False,
                },
                ensure_ascii=False,
            ),
        )
    if not isinstance(alias, dict):
        fail("GitHub did not return the stable alias release")
    return alias


def remove_non_metadata_assets(*, repo: str, alias: dict) -> None:
    for asset in alias.get("assets", []):
        if not isinstance(asset, dict) or asset.get("name") == METADATA_NAME:
            continue
        asset_id = asset.get("id")
        if not isinstance(asset_id, int):
            fail("stable alias contains an asset without a numeric ID")
        run(
            [
                "gh",
                "api",
                "--method",
                "DELETE",
                f"repos/{repo}/releases/assets/{asset_id}",
            ]
        )


def download_public_metadata(
    *,
    url: str,
    expected: dict,
    attempts: int = 5,
    delay_seconds: float = 2,
) -> dict:
    if attempts < 1:
        fail("stable metadata verification needs at least one attempt")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                status = getattr(response, "status", None)
                if status is not None and status != 200:
                    raise RuntimeError(f"HTTP {status}")
                downloaded = json.loads(response.read().decode("utf-8"))
            if not isinstance(downloaded, dict):
                raise ValueError("endpoint returned a non-object JSON value")
            if downloaded != expected:
                raise ValueError("endpoint still serves different metadata")
            return downloaded
        except Exception as error:  # noqa: BLE001 - bounded public endpoint verification
            last_error = error
            if attempt < attempts:
                time.sleep(delay_seconds)
    fail(
        "stable metadata endpoint is not readable after "
        f"{attempts} attempts: {last_error}"
    )


def upload_and_verify_alias(
    *,
    repo: str,
    alias_tag: str,
    source_tag: str,
    metadata_path: Path,
) -> dict:
    run(
        [
            "gh",
            "release",
            "upload",
            alias_tag,
            str(metadata_path),
            "--repo",
            repo,
            "--clobber",
        ]
    )
    alias = release_by_tag(repo, alias_tag)
    if alias is None:
        fail("stable alias disappeared after metadata upload")
    if alias.get("draft") is not False or alias.get("prerelease") is not True:
        fail("stable alias must be a published prerelease")
    names = asset_names(alias)
    if names != {METADATA_NAME}:
        fail(f"stable alias must contain only latest.json, got: {sorted(names)!r}")

    url = f"https://github.com/{repo}/releases/download/{quote(alias_tag, safe='')}/{METADATA_NAME}"
    expected = json.loads(metadata_path.read_text(encoding="utf-8"))
    downloaded = download_public_metadata(url=url, expected=expected)
    for entry in downloaded.get("platforms", {}).values():
        if isinstance(entry, dict) and f"/download/{quote(source_tag, safe='')}/" not in str(entry.get("url") or ""):
            fail("stable metadata endpoint does not preserve the signed source tag")
    return alias


def refresh_stable_channel(
    *,
    repo: str,
    source_tag: str = "",
    alias_tag: str = DEFAULT_ALIAS_TAG,
    work_dir: Path,
) -> tuple[str, dict]:
    if not os.environ.get("GH_TOKEN"):
        fail("GH_TOKEN is required")
    repo = validate_repo(repo)
    if not re.fullmatch(r"[^/]+", alias_tag.strip()) or not alias_tag.strip():
        fail(f"invalid stable alias tag: {alias_tag!r}")
    releases = list_releases(repo)
    source_release = select_signed_release(releases, source_tag)
    source_tag = str(source_release.get("tag_name") or "")
    metadata = download_source_metadata(
        repo=repo,
        source_tag=source_tag,
        work_dir=work_dir,
    )
    validate_metadata(
        metadata,
        repo=repo,
        source_tag=source_tag,
        source_release=source_release,
    )
    alias = upsert_alias(
        repo=repo,
        alias_tag=alias_tag,
        source_release=source_release,
    )
    remove_non_metadata_assets(repo=repo, alias=alias)
    metadata_path = work_dir / METADATA_NAME
    alias = upload_and_verify_alias(
        repo=repo,
        alias_tag=alias_tag,
        source_tag=source_tag,
        metadata_path=metadata_path,
    )
    print(
        f"Stable channel refreshed: {alias_tag} -> {source_tag} "
        f"({len(alias.get('assets', []))} metadata asset)",
        flush=True,
    )
    return source_tag, alias


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-tag", default="")
    parser.add_argument("--alias-tag", default=DEFAULT_ALIAS_TAG)
    parser.add_argument(
        "--work-dir", type=Path, default=Path("stable-channel-check")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    refresh_stable_channel(
        repo=args.repo,
        source_tag=args.source_tag,
        alias_tag=args.alias_tag,
        work_dir=args.work_dir.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
