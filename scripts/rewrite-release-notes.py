#!/usr/bin/env python3
"""Regenerate a published Release body from its actual assets."""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import tempfile
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def load_script(name: str, module_name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        fail(f"cannot load release helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def previous_field(release: dict, label: str) -> str:
    body = str(release.get("body") or "")
    match = re.search(rf"^- {re.escape(label)}：`([^`]+)`\s*$", body, re.MULTILINE)
    if match is None:
        match = re.search(rf"^- {re.escape(label)}：(.+?)\s*$", body, re.MULTILINE)
    return match.group(1).strip() if match else ""


def required_field(explicit: str, release: dict, *labels: str) -> str:
    value = explicit.strip()
    if not value:
        for label in labels:
            value = previous_field(release, label)
            if value:
                break
    if not value:
        fail(f"missing release field: {' / '.join(labels)}")
    return value


def version_from_tag(tag: str) -> str:
    unsigned = re.fullmatch(r"unsigned-v(.+)-r[1-9][0-9]*", tag)
    if unsigned:
        return unsigned.group(1)
    return tag.removeprefix("v")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--platforms", default="")
    parser.add_argument("--highlights-file", type=Path)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()

    if not os.environ.get("GH_TOKEN"):
        fail("GH_TOKEN is required")
    repo = args.repo.strip().strip("/")
    tag = args.tag.strip()
    if not re.fullmatch(r"[^/]+/[^/]+", repo) or not tag or "/" in tag:
        fail("invalid repository or release tag")

    finalizer = load_script("finalize-unsigned-release.py", "fanqie_unsigned_finalizer")
    preparer = load_script("prepare-release-artifacts.py", "fanqie_release_preparer")
    directory_context = tempfile.TemporaryDirectory() if args.work_dir is None else None
    directory = (
        Path(directory_context.name)
        if directory_context is not None
        else args.work_dir.resolve()
    )
    directory.mkdir(parents=True, exist_ok=True)
    release_path = directory / "release.json"
    notes_path = directory / "release-notes.md"

    database_id = finalizer.release_id(repo, tag)
    release = finalizer.fetch_release(repo, database_id, release_path)
    if release.get("draft") is True:
        fail("rewrite-release-notes only handles an already published release")

    version = args.version.strip() or version_from_tag(tag)
    source_ref = required_field(args.source_ref, release, "源码引用")
    source_commit = required_field(args.source_commit, release, "源码提交")
    platforms = required_field(args.platforms, release, "构建平台", "计划平台")
    highlights = finalizer.normalized_highlights(args.highlights_file)

    if re.fullmatch(r"unsigned-v[^/]+-r[1-9][0-9]*", tag):
        updater_available = finalizer.has_updater_metadata(release)
        finalizer.validate_assets(release, platforms, allow_updater=updater_available)
        appendix = finalizer.generate_finalizer_appendix(
            release=release,
            repo=repo,
            tag=tag,
            version=version,
            source_ref=source_ref,
            source_commit=source_commit,
            platforms=platforms,
            mode="prerelease" if release.get("prerelease") else "formal",
            highlights=highlights,
        )
        notes = finalizer.append_finalizer(str(release.get("body") or ""), appendix)
    else:
        notes = preparer.generate_notes(
            release,
            repo=repo,
            tag=tag,
            version=version,
            source_ref=source_ref,
            source_commit=source_commit,
            platforms=platforms,
            highlights=highlights,
        )

    notes_path.write_text(notes, encoding="utf-8", newline="\n")
    run(
        [
            "gh",
            "release",
            "edit",
            tag,
            "--repo",
            repo,
            "--notes-file",
            str(notes_path),
        ]
    )
    updated = finalizer.fetch_release(repo, database_id, release_path)
    if str(updated.get("body") or "").rstrip() != notes.rstrip():
        fail("GitHub Release body did not match regenerated notes")
    print(
        f"Release notes refreshed: https://github.com/{repo}/releases/tag/{tag}",
        flush=True,
    )
    if directory_context is not None:
        directory_context.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
