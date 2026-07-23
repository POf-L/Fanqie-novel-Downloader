#!/usr/bin/env python3
"""Finalize an existing draft GitHub Release without rebuilding binaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
NORMALIZER = ROOT / "scripts" / "normalize-updater-metadata.py"
PREPARER = ROOT / "scripts" / "prepare-release-artifacts.py"
MANIFEST_NAME = "SHA256SUMS-release.txt"
ASSET_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


def fail(message: str) -> None:
    raise SystemExit(message)


def run(command: list[str], *, capture: bool = False) -> str:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if result.stdout is not None else ""


def gh_json(arguments: list[str]) -> object:
    output = run(["gh", *arguments], capture=True)
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        fail(f"GitHub CLI returned invalid JSON: {error}")


def release_id(repo: str, tag: str) -> int:
    payload = gh_json(
        [
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "databaseId,tagName",
        ]
    )
    if not isinstance(payload, dict) or payload.get("tagName") != tag:
        fail(f"cannot resolve release tag {tag!r}")
    value = payload.get("databaseId")
    if not isinstance(value, int):
        fail(f"release {tag!r} has no numeric database ID")
    return value


def fetch_release(repo: str, database_id: int, path: Path) -> dict:
    release: object = None
    assets: list[dict] = []
    pending: list[str] = []
    for attempt in range(5):
        release = gh_json(["api", f"repos/{repo}/releases/{database_id}"])
        pages = gh_json(
            [
                "api",
                "--paginate",
                "--slurp",
                f"repos/{repo}/releases/{database_id}/assets?per_page=100",
            ]
        )
        if not isinstance(release, dict) or not isinstance(pages, list):
            fail("GitHub release API returned an unexpected payload")
        assets = []
        for page in pages:
            if not isinstance(page, list) or not all(
                isinstance(asset, dict) for asset in page
            ):
                fail("GitHub release asset API returned an unexpected page")
            assets.extend(page)
        pending = [
            str(asset.get("name") or "<unnamed>")
            for asset in assets
            if ASSET_DIGEST_RE.fullmatch(str(asset.get("digest") or "")) is None
        ]
        if not pending:
            break
        if attempt < 4:
            print(
                "Waiting for GitHub asset digests: " + ", ".join(pending),
                flush=True,
            )
            time.sleep(2)
    if not isinstance(release, dict):
        fail("GitHub release API did not return a release")
    if pending:
        fail("GitHub did not provide SHA-256 digests for: " + ", ".join(pending))
    release["assets"] = assets
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return release


def run_normalizer(metadata: Path, release: Path, repo: str, tag: str) -> None:
    base = [
        sys.executable,
        str(NORMALIZER),
        "--metadata",
        str(metadata),
        "--assets",
        str(release),
        "--repo",
        repo,
        "--tag",
        tag,
    ]
    run(base)
    run([*base, "--check"])


def run_preparer(
    *,
    release: Path,
    repo: str,
    tag: str,
    manifest: Path,
    notes: Path | None = None,
    version: str = "",
    source_ref: str = "",
    source_commit: str = "",
    platforms: str = "",
    highlights: Path | None = None,
    check: bool = False,
) -> None:
    command = [
        sys.executable,
        str(PREPARER),
        "--release",
        str(release),
        "--repo",
        repo,
        "--tag",
        tag,
        "--manifest",
        str(manifest),
    ]
    if check:
        command.append("--check")
    else:
        if notes is None:
            fail("release notes path is required while preparing artifacts")
        command.extend(["--notes", str(notes)])
        for flag, value in (
            ("--version", version),
            ("--source-ref", source_ref),
            ("--source-commit", source_commit),
            ("--platforms", platforms),
        ):
            if value.strip():
                command.extend([flag, value.strip()])
        if highlights is not None:
            command.extend(["--highlights-file", str(highlights)])
    run(command)


def validate_release_identity(release: dict, tag: str, *, draft: bool) -> None:
    if release.get("tag_name") != tag:
        fail(
            f"release tag mismatch: expected {tag!r}, "
            f"got {release.get('tag_name')!r}"
        )
    if release.get("draft") is not draft:
        state = "draft" if draft else "published"
        fail(f"release {tag!r} is not {state}")


def verify_published_urls(release: dict, repo: str, tag: str) -> None:
    prefix = (
        f"https://github.com/{repo}/releases/download/{quote(tag, safe='')}/"
    )
    for asset in release.get("assets", []):
        if not isinstance(asset, dict):
            fail("published release contains a malformed asset")
        name = str(asset.get("name") or "")
        expected = prefix + quote(name, safe="")
        actual = str(asset.get("browser_download_url") or "")
        if actual != expected:
            fail(
                f"published asset URL is not canonical for {name!r}: {actual!r}"
            )


def append_summary(
    *, repo: str, tag: str, source_commit: str, release: dict
) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not path:
        return
    assets = release.get("assets", [])
    with Path(path).open("a", encoding="utf-8", newline="\n") as output:
        output.write(
            "## Finalized Release\n\n"
            f"- Release: [{tag}](https://github.com/{repo}/releases/tag/{tag})\n"
            f"- Source commit: `{source_commit}`\n"
            f"- Assets: `{len(assets)}`\n"
            f"- Prerelease: `{str(bool(release.get('prerelease'))).lower()}`\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--platforms", default="")
    parser.add_argument("--highlights-file", type=Path)
    parser.add_argument("--work-dir", type=Path, default=Path("release-check"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.strip().strip("/")
    tag = args.tag.strip()
    if not re.fullmatch(r"[^/]+/[^/]+", repo):
        fail(f"invalid GitHub repository: {repo!r}")
    if not tag or "/" in tag:
        fail(f"invalid GitHub release tag: {tag!r}")
    if not os.environ.get("GH_TOKEN"):
        fail("GH_TOKEN is required")

    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    release_path = work_dir / "release.json"
    metadata_path = work_dir / "latest.json"
    manifest_path = work_dir / MANIFEST_NAME
    notes_path = work_dir / "release-notes.md"

    database_id = release_id(repo, tag)
    release = fetch_release(repo, database_id, release_path)
    validate_release_identity(release, tag, draft=True)
    prerelease = bool(release.get("prerelease"))
    asset_names = {
        str(asset.get("name") or "")
        for asset in release.get("assets", [])
        if isinstance(asset, dict)
    }
    if any(name.lower().endswith(".sig") for name in asset_names) and (
        "latest.json" not in asset_names
    ):
        fail("release has signed updater assets but no latest.json")

    if "latest.json" in asset_names:
        run(
            [
                "gh",
                "release",
                "download",
                tag,
                "--repo",
                repo,
                "--pattern",
                "latest.json",
                "--dir",
                str(work_dir),
                "--clobber",
            ]
        )
        run_normalizer(metadata_path, release_path, repo, tag)
        run(
            [
                "gh",
                "release",
                "upload",
                tag,
                str(metadata_path),
                "--repo",
                repo,
                "--clobber",
            ]
        )
        release = fetch_release(repo, database_id, release_path)

    run_preparer(
        release=release_path,
        repo=repo,
        tag=tag,
        manifest=manifest_path,
        notes=notes_path,
        version=args.version,
        source_ref=args.source_ref,
        source_commit=args.source_commit,
        platforms=args.platforms,
        highlights=args.highlights_file,
    )
    run(
        [
            "gh",
            "release",
            "upload",
            tag,
            str(manifest_path),
            "--repo",
            repo,
            "--clobber",
        ]
    )

    release = fetch_release(repo, database_id, release_path)
    validate_release_identity(release, tag, draft=True)
    run_preparer(
        release=release_path,
        repo=repo,
        tag=tag,
        manifest=manifest_path,
        check=True,
    )
    if "latest.json" in asset_names:
        run_normalizer(metadata_path, release_path, repo, tag)

    publish = [
        "gh",
        "release",
        "edit",
        tag,
        "--repo",
        repo,
        "--title",
        f"番茄小说下载器 {args.version.strip() or tag.removeprefix('v')}",
        "--notes-file",
        str(notes_path),
        "--draft=false",
    ]
    if not prerelease:
        publish.append("--latest")
    run(publish)

    published = fetch_release(repo, database_id, release_path)
    validate_release_identity(published, tag, draft=False)
    if bool(published.get("prerelease")) != prerelease:
        fail("release prerelease state changed during finalization")
    verify_published_urls(published, repo, tag)
    run_preparer(
        release=release_path,
        repo=repo,
        tag=tag,
        manifest=manifest_path,
        check=True,
    )
    if "latest.json" in asset_names:
        run_normalizer(metadata_path, release_path, repo, tag)

    source_commit = args.source_commit.strip()
    if not source_commit:
        body = str(published.get("body") or "")
        match = re.search(r"^- 源码提交：`([^`]+)`\s*$", body, re.MULTILINE)
        source_commit = match.group(1) if match else "unknown"
    if source_commit not in str(published.get("body") or ""):
        fail("published release notes do not contain the source commit")
    if not prerelease:
        latest = gh_json(["api", f"repos/{repo}/releases/latest"])
        if not isinstance(latest, dict) or latest.get("tag_name") != tag:
            fail(f"published stable release {tag!r} is not GitHub's latest release")

    append_summary(
        repo=repo, tag=tag, source_commit=source_commit, release=published
    )
    print(
        f"Release finalized: https://github.com/{repo}/releases/tag/{tag} "
        f"({len(published.get('assets', []))} assets)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
