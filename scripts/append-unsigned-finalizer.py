#!/usr/bin/env python3
"""Append or refresh the managed device guide on a published unsigned Release."""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def load_finalizer():
    path = Path(__file__).with_name("finalize-unsigned-release.py")
    spec = importlib.util.spec_from_file_location("fanqie_unsigned_finalizer", path)
    if spec is None or spec.loader is None:
        fail(f"cannot load unsigned finalizer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def required_field(explicit: str, release: dict, finalizer, *labels: str) -> str:
    value = explicit.strip()
    if not value:
        for label in labels:
            value = finalizer.previous_field(release, label)
            if value:
                break
    if not value:
        fail(f"missing release field: {' / '.join(labels)}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--platforms", default="")
    parser.add_argument("--highlights-file", type=Path)
    parser.add_argument(
        "--work-dir", type=Path, default=Path("unsigned-finalizer-check")
    )
    args = parser.parse_args()

    repo = args.repo.strip().strip("/")
    tag = args.tag.strip()
    if not os.environ.get("GH_TOKEN"):
        fail("GH_TOKEN is required")
    if not re.fullmatch(r"[^/]+/[^/]+", repo):
        fail(f"invalid GitHub repository: {repo!r}")
    if not re.fullmatch(r"unsigned-v[^/]+-r[1-9][0-9]*", tag):
        fail(f"invalid isolated unsigned release tag: {tag!r}")

    finalizer = load_finalizer()
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    release_path = work_dir / "release.json"
    notes_path = work_dir / "release-notes.md"
    database_id = finalizer.release_id(repo, tag)
    release = finalizer.fetch_release(repo, database_id, release_path)
    if release.get("draft") is not False:
        fail("append-unsigned-finalizer only handles a published Release")

    version = finalizer.version_field(args.version, release, tag)
    source_ref = required_field(args.source_ref, release, finalizer, "源码引用")
    source_commit = required_field(args.source_commit, release, finalizer, "源码提交")
    platforms = required_field(
        args.platforms, release, finalizer, "构建平台", "计划平台"
    )
    updater_available = finalizer.has_updater_metadata(release)
    finalizer.validate_assets(
        release, platforms, allow_updater=updater_available
    )
    appendix = finalizer.generate_finalizer_appendix(
        release=release,
        repo=repo,
        tag=tag,
        version=version,
        source_ref=source_ref,
        source_commit=source_commit,
        platforms=platforms,
        mode="prerelease" if release.get("prerelease") else "formal",
        highlights=finalizer.normalized_highlights(args.highlights_file),
    )
    notes = finalizer.append_finalizer(
        str(release.get("body") or ""),
        appendix,
        allow_legacy_draft=True,
    )
    finalizer.verify_device_guide(
        notes,
        platforms=platforms,
        updater_available=updater_available,
        mode="prerelease" if release.get("prerelease") else "formal",
    )
    notes_path.write_text(notes, encoding="utf-8", newline="\n")
    subprocess.run(
        [
            "gh", "release", "edit", tag, "--repo", repo,
            "--notes-file", str(notes_path),
        ],
        check=True,
    )

    updated = finalizer.fetch_release(repo, database_id, release_path)
    updated_notes = str(updated.get("body") or "")
    if updated_notes.rstrip() != notes.rstrip():
        fail("GitHub Release body did not preserve the appended unsigned finalizer")
    finalizer.verify_device_guide(
        updated_notes,
        platforms=platforms,
        updater_available=updater_available,
        mode="prerelease" if updated.get("prerelease") else "formal",
    )
    print(
        f"Unsigned finalizer appended: https://github.com/{repo}/releases/tag/{tag}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
