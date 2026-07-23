#!/usr/bin/env python3
"""Rewrite Tauri updater URLs to public GitHub release download URLs."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


API_ASSET_RE = re.compile(r"/releases/assets/(\d+)(?:/|$)")


def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read JSON {path}: {error}") from error


def release_assets(payload: object) -> tuple[dict[str, dict], dict[str, dict]]:
    if isinstance(payload, dict):
        assets = payload.get("assets")
    else:
        assets = payload
    if not isinstance(assets, list):
        raise SystemExit("release asset JSON must contain an assets array")

    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").strip()
        if not name:
            continue
        by_name[name] = asset
        asset_id = asset.get("id")
        if asset_id is not None:
            by_id[str(asset_id)] = asset
    if not by_name:
        raise SystemExit("release asset JSON does not contain any named assets")
    return by_id, by_name


def expected_download_prefix(repo: str, tag: str) -> str:
    repo = repo.strip().strip("/")
    tag = tag.strip()
    if not re.fullmatch(r"[^/]+/[^/]+", repo):
        raise SystemExit(f"invalid GitHub repository: {repo!r}")
    if not tag or "/" in tag:
        raise SystemExit(f"invalid GitHub release tag: {tag!r}")
    return f"https://github.com/{repo}/releases/download/{quote(tag, safe='')}/"


def public_asset_url(asset: dict, prefix: str) -> str:
    name = str(asset.get("name") or "").strip()
    if not name:
        raise SystemExit("release asset has no name")
    if name == "latest.json" or name.endswith(".sig"):
        raise SystemExit(f"updater entry points to a metadata/signature asset: {name}")

    # Draft release assets use an ephemeral ``untagged-*`` download path.  The
    # authenticated release payload is authoritative for the asset name, but
    # its browser URL is not stable until the draft is published.
    return prefix + quote(name, safe="")


def asset_for_entry(
    entry: dict, by_id: dict[str, dict], by_name: dict[str, dict]
) -> dict:
    raw_url = str(entry.get("url") or "").strip()
    match = API_ASSET_RE.search(urlparse(raw_url).path)
    if match:
        asset = by_id.get(match.group(1))
        if asset is not None:
            return asset
        raise SystemExit(
            f"updater URL references missing release asset id {match.group(1)}"
        )

    # Tauri versions that already emit browser URLs can be normalized again.
    path_name = unquote(urlparse(raw_url).path.rstrip("/").rsplit("/", 1)[-1])
    if path_name in by_name:
        return by_name[path_name]

    declared_name = str(entry.get("name") or "").strip()
    if declared_name in by_name:
        return by_name[declared_name]

    raise SystemExit(
        "cannot map updater entry to a release asset; "
        f"URL={raw_url!r}, name={declared_name!r}"
    )


def normalize(
    metadata: dict,
    by_id: dict[str, dict],
    by_name: dict[str, dict],
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

    platforms = metadata.get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        raise SystemExit("latest.json does not contain updater platforms")

    changed = False
    for platform, entry in platforms.items():
        if not isinstance(entry, dict):
            raise SystemExit(f"invalid updater entry: {platform}")
        if not str(entry.get("signature") or "").strip():
            raise SystemExit(f"updater entry has no signature: {platform}")
        asset = asset_for_entry(entry, by_id, by_name)
        expected = public_asset_url(asset, prefix)
        current = str(entry.get("url") or "").strip()
        if check:
            if current != expected:
                raise SystemExit(
                    f"updater URL is not normalized for {platform}: {current!r}"
                )
        elif current != expected:
            entry["url"] = expected
            changed = True
    return changed


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
    parser.add_argument("--repo", required=True, help="OWNER/REPOSITORY")
    parser.add_argument("--tag", required=True)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless every updater URL already uses the public release URL",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    metadata = read_json(args.metadata)
    if not isinstance(metadata, dict):
        raise SystemExit("latest.json must contain a JSON object")
    assets_payload = read_json(args.assets)
    by_id, by_name = release_assets(assets_payload)
    prefix = expected_download_prefix(args.repo, args.tag)
    changed = normalize(
        metadata,
        by_id,
        by_name,
        prefix,
        args.tag.removeprefix("v"),
        check=args.check,
    )
    if not args.check and changed:
        write_json(args.metadata, metadata)
    print(
        f"Updater metadata {'already normalized' if args.check else 'normalized'}: "
        f"{len(metadata['platforms'])} platform entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
