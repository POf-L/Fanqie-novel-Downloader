#!/usr/bin/env python3
"""Resolve the pre-created draft release and move its assets by release ID.

release-bootstrap creates exactly one Draft for a tag and publishes its numeric
ID as a job output.  Every later upload goes through this script with that ID.
Nothing here looks a Draft up by tag for an upload, and nothing here creates a
release: a missing or mismatched ID is a hard failure.  (Looking Drafts up by
tag is what used to split one release into two same-tag Drafts: tauri-action
would miss the bootstrap Draft in the release list and create a second one.)

Subcommands:
  resolve  Find the single release carrying a tag (bootstrap only).
  upload   Upload files to the release, replacing same-name assets.
  delete   Delete named assets from the release; missing names are fine.
  list     Print the release's asset names, one per line.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import quote


GhRunner = Callable[[Sequence[str], "str | None"], str]

RELEASE_PAGE_SIZE = 30
# The full /releases dump is too large to fetch reliably from CI runners; the
# Draft just created by release-bootstrap is always among the newest entries.
DEFAULT_MAX_PAGES = 5
ASSET_PAGE_SIZE = 100
TRANSIENT_RE = re.compile(
    r"\b(429|5\d\d)\b|rate limit|secondary rate|abuse detection|"
    r"try again later|temporarily unavailable|timed out|timeout|"
    r"connection reset|EOF",
    re.IGNORECASE,
)


class ReleaseAssetError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ReleaseAssetError(message)


def default_gh(arguments: Sequence[str], input_path: str | None = None) -> str:
    command = ["gh", *arguments]
    if input_path is not None:
        command.extend(["--input", input_path])
    result = subprocess.run(
        command,
        check=False,
        # gh prints UTF-8 (release bodies are Chinese); never fall back to the
        # Windows ANSI code page.
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, command, result.stdout, result.stderr
        )
    return result.stdout


def looks_transient(error: subprocess.CalledProcessError) -> bool:
    stdout = error.stdout if isinstance(error.stdout, str) else ""
    stderr = error.stderr if isinstance(error.stderr, str) else ""
    return TRANSIENT_RE.search(f"{stdout}\n{stderr}") is not None


def describe(error: subprocess.CalledProcessError) -> str:
    stderr = error.stderr if isinstance(error.stderr, str) else ""
    stdout = error.stdout if isinstance(error.stdout, str) else ""
    text = (stderr or stdout).strip()
    return text.splitlines()[-1] if text else f"exit code {error.returncode}"


class ReleaseClient:
    def __init__(
        self,
        repo: str,
        *,
        gh: GhRunner = default_gh,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 4,
        base_delay: float = 4.0,
    ) -> None:
        repo = repo.strip().strip("/")
        if not re.fullmatch(r"[^/\s]+/[^/\s]+", repo):
            fail(f"invalid GitHub repository: {repo!r}")
        if attempts < 1:
            fail("attempts must be at least 1")
        self.repo = repo
        self._gh = gh
        self._sleep = sleep
        self.attempts = attempts
        self.base_delay = base_delay

    def call(self, arguments: Sequence[str], input_path: str | None = None) -> str:
        for attempt in range(1, self.attempts + 1):
            try:
                return self._gh(list(arguments), input_path)
            except subprocess.CalledProcessError as error:
                if attempt >= self.attempts or not looks_transient(error):
                    fail(f"gh {' '.join(arguments)} failed: {describe(error)}")
                delay = self.base_delay * (2 ** (attempt - 1))
                print(
                    f"transient GitHub failure (attempt {attempt}/{self.attempts}); "
                    f"retrying in {delay:g}s: {describe(error)}",
                    file=sys.stderr,
                    flush=True,
                )
                self._sleep(delay)
        fail("unreachable retry state")
        return ""

    def json(self, arguments: Sequence[str]) -> object:
        output = self.call(arguments)
        try:
            return json.loads(output or "null")
        except json.JSONDecodeError as error:
            fail(f"GitHub returned invalid JSON for {' '.join(arguments)}: {error}")
        return None

    # -- lookup ---------------------------------------------------------

    def releases_with_tag(self, tag: str, *, max_pages: int) -> list[dict]:
        matches: list[dict] = []
        for page in range(1, max_pages + 1):
            chunk = self.json(
                [
                    "api",
                    f"repos/{self.repo}/releases?per_page={RELEASE_PAGE_SIZE}&page={page}",
                ]
            )
            if not isinstance(chunk, list):
                fail("GitHub returned an invalid release list")
            matches.extend(
                item
                for item in chunk
                if isinstance(item, dict) and item.get("tag_name") == tag
            )
            if len(chunk) < RELEASE_PAGE_SIZE:
                break
        return matches

    def resolve(
        self,
        tag: str,
        *,
        max_pages: int = DEFAULT_MAX_PAGES,
        lookups: int = 6,
        lookup_delay: float = 5.0,
        require_draft: bool = False,
    ) -> int:
        validate_tag(tag)
        matches: list[dict] = []
        for lookup in range(1, lookups + 1):
            matches = self.releases_with_tag(tag, max_pages=max_pages)
            if matches:
                break
            if lookup < lookups:
                # The release list is eventually consistent right after create.
                print(
                    f"release {tag} not listed yet (lookup {lookup}/{lookups}); "
                    f"retrying in {lookup_delay:g}s",
                    file=sys.stderr,
                    flush=True,
                )
                self._sleep(lookup_delay)
        if not matches:
            fail(f"no release found for tag {tag!r}")
        if len(matches) > 1:
            ids = ", ".join(str(item.get("id")) for item in matches)
            fail(
                f"tag {tag!r} is carried by {len(matches)} releases ({ids}); "
                "consolidate them with 'Maintenance - merge split unsigned drafts' "
                "before building again"
            )
        release = matches[0]
        if require_draft and release.get("draft") is not True:
            fail(f"release for tag {tag!r} is not a draft")
        return parse_release_id(str(release.get("id", "")))

    def release(self, release_id: int, tag: str) -> dict:
        payload = self.json(["api", f"repos/{self.repo}/releases/{release_id}"])
        if not isinstance(payload, dict):
            fail(f"release {release_id} returned an invalid payload")
        if payload.get("id") != release_id:
            fail(f"release {release_id} returned a different ID: {payload.get('id')!r}")
        if payload.get("tag_name") != tag:
            fail(
                f"release {release_id} carries tag {payload.get('tag_name')!r}, "
                f"expected {tag!r}; refusing to touch another release"
            )
        return payload

    def assets(self, release_id: int) -> list[dict]:
        collected: list[dict] = []
        page = 1
        while True:
            chunk = self.json(
                [
                    "api",
                    f"repos/{self.repo}/releases/{release_id}/assets"
                    f"?per_page={ASSET_PAGE_SIZE}&page={page}",
                ]
            )
            if not isinstance(chunk, list):
                fail(f"release {release_id} returned an invalid asset list")
            collected.extend(item for item in chunk if isinstance(item, dict))
            if len(chunk) < ASSET_PAGE_SIZE:
                return collected
            page += 1

    # -- mutations ------------------------------------------------------

    def delete_asset(self, asset: dict) -> None:
        asset_id = asset.get("id")
        if not isinstance(asset_id, int):
            fail(f"asset {asset.get('name')!r} has no numeric ID")
        self.call(
            [
                "api",
                "--method",
                "DELETE",
                f"repos/{self.repo}/releases/assets/{asset_id}",
            ]
        )

    def delete(self, release_id: int, tag: str, names: Sequence[str]) -> list[str]:
        self.release(release_id, tag)
        wanted = set(names)
        deleted = []
        for asset in self.assets(release_id):
            if asset.get("name") in wanted:
                self.delete_asset(asset)
                deleted.append(str(asset["name"]))
        return deleted

    def upload(self, release_id: int, tag: str, files: Sequence[Path]) -> list[str]:
        self.release(release_id, tag)
        paths = [Path(path) for path in files]
        if not paths:
            fail("no files to upload")
        names = [path.name for path in paths]
        if len(set(names)) != len(names):
            fail("refusing to upload two files with the same asset name")
        for path in paths:
            if not path.is_file():
                fail(f"upload source is not a file: {path}")
        uploaded = []
        for path in paths:
            self._upload_one(release_id, path)
            uploaded.append(path.name)
        return uploaded

    def _upload_one(self, release_id: int, path: Path) -> None:
        name = path.name
        url = (
            f"https://uploads.github.com/repos/{self.repo}/releases/{release_id}"
            f"/assets?name={quote(name, safe='')}"
        )
        for attempt in range(1, self.attempts + 1):
            # Clobber: drop a same-name asset first (also clears a half-finished
            # upload left behind by a previous failed attempt).
            for asset in self.assets(release_id):
                if asset.get("name") == name:
                    self.delete_asset(asset)
            try:
                self._gh(
                    [
                        "api",
                        "--method",
                        "POST",
                        "-H",
                        "Content-Type: application/octet-stream",
                        url,
                    ],
                    str(path),
                )
                print(f"uploaded {name} to release {release_id}", flush=True)
                return
            except subprocess.CalledProcessError as error:
                if attempt >= self.attempts:
                    fail(f"uploading {name} failed: {describe(error)}")
                delay = self.base_delay * (2 ** (attempt - 1))
                print(
                    f"upload of {name} failed (attempt {attempt}/{self.attempts}); "
                    f"retrying in {delay:g}s: {describe(error)}",
                    file=sys.stderr,
                    flush=True,
                )
                self._sleep(delay)


def validate_tag(tag: str) -> None:
    if not tag or "/" in tag or tag != tag.strip():
        fail(f"invalid release tag: {tag!r}")


def parse_release_id(value: str) -> int:
    text = (value or "").strip()
    if not text:
        fail(
            "missing release ID: release-bootstrap must provide the pre-created "
            "Draft's ID; refusing to look a Draft up by tag or create one"
        )
    if not re.fullmatch(r"[1-9][0-9]*", text):
        fail(f"invalid release ID: {value!r}")
    return int(text)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--repo", required=True)
    resolve.add_argument("--tag", required=True)
    resolve.add_argument("--require-draft", action="store_true")
    resolve.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    resolve.add_argument("--github-output", type=Path)

    for name in ("upload", "delete", "list"):
        command = sub.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--release-id", required=True)
        command.add_argument("--tag", required=True)
        if name == "upload":
            command.add_argument("files", nargs="+", type=Path)
        elif name == "delete":
            command.add_argument("names", nargs="+")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None, *, client: ReleaseClient | None = None) -> int:
    args = parse_args(argv)
    try:
        client = client or ReleaseClient(args.repo)
        if args.command == "resolve":
            release_id = client.resolve(
                args.tag,
                max_pages=args.max_pages,
                require_draft=args.require_draft,
            )
            print(release_id)
            if args.github_output is not None:
                with args.github_output.open("a", encoding="utf-8") as handle:
                    handle.write(f"release_id={release_id}\n")
            return 0

        validate_tag(args.tag)
        release_id = parse_release_id(args.release_id)
        if args.command == "upload":
            client.upload(release_id, args.tag, args.files)
        elif args.command == "delete":
            for name in client.delete(release_id, args.tag, args.names):
                print(f"deleted {name} from release {release_id}", flush=True)
        else:
            client.release(release_id, args.tag)
            for asset in client.assets(release_id):
                print(asset.get("name", ""))
        return 0
    except ReleaseAssetError as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
