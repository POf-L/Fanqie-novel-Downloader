#!/usr/bin/env python3
"""Validate and publish an unsigned draft GitHub Release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote


MANIFEST_NAME = "SHA256SUMS-unsigned.txt"
DIGEST_RE = re.compile(r"sha256:([0-9a-f]{64})\Z")
FORBIDDEN_EXACT = {"latest.json", "sha256sums-release.txt"}
FORBIDDEN_SUFFIXES = (
    ".sig",
    ".nsis.zip",
    ".msi.zip",
    ".app.tar.gz",
    ".appimage.tar.gz",
)
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
CLI_ASSET_RE = re.compile(r"(?:^|[-_. ])cli(?:[-_. ]|$)", re.IGNORECASE)


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
    if not isinstance(value, int) or value < 1:
        fail(f"release {tag!r} has no numeric database ID")
    return value


def latest_tag(repo: str) -> str:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/releases/latest"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return ""
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        fail(f"GitHub latest release API returned invalid JSON: {error}")
    return str(payload.get("tag_name") or "") if isinstance(payload, dict) else ""


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
            if DIGEST_RE.fullmatch(str(asset.get("digest") or "")) is None
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


def previous_field(release: dict, label: str) -> str:
    body = str(release.get("body") or "")
    match = re.search(rf"^- {re.escape(label)}：`([^`]+)`\s*$", body, re.MULTILINE)
    if match is None:
        match = re.search(
            rf"^- {re.escape(label)}：(.+?)\s*$", body, re.MULTILINE
        )
    return match.group(1).strip() if match else ""


def release_field(explicit: str, release: dict, label: str) -> str:
    value = explicit.strip() or previous_field(release, label)
    if not value:
        fail(f"missing {label}; pass it explicitly or retain it in draft notes")
    return value


def version_field(explicit: str, release: dict, tag: str) -> str:
    value = explicit.strip() or previous_field(release, "正在构建版本")
    if value:
        return value
    match = re.fullmatch(r"unsigned-v(.+)-r[1-9][0-9]*", tag)
    if match is None:
        fail("cannot derive version from unsigned release tag")
    return match.group(1)


def payload_assets(release: dict) -> list[dict]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        fail("release does not contain an asset list")
    payload = [
        asset
        for asset in assets
        if str(asset.get("name") or "").lower() != MANIFEST_NAME.lower()
    ]
    names = [str(asset.get("name") or "") for asset in payload]
    if not names or any(not name for name in names):
        fail("unsigned release has no valid assets")
    if len(names) != len(set(names)):
        fail("unsigned release contains duplicate asset names")
    return payload


def is_updater_asset(name: str) -> bool:
    lowered = name.lower()
    return lowered in FORBIDDEN_EXACT or lowered.endswith(FORBIDDEN_SUFFIXES)


def require_asset(
    names: list[str], label: str, *needles: str, suffix: str | None = None
) -> None:
    matches = [
        name
        for name in names
        if all(needle.lower() in name.lower() for needle in needles)
        and (suffix is None or name.lower().endswith(suffix.lower()))
    ]
    if not matches:
        fail(f"unsigned release is missing the {label} asset")


def selected_platforms(value: str) -> set[str]:
    selected = {item.strip().lower() for item in value.split(",") if item.strip()}
    if not selected:
        fail("release does not identify any build platform")
    return selected


def validate_assets(release: dict, platforms: str) -> tuple[list[dict], list[str]]:
    payload = payload_assets(release)
    names = [str(asset["name"]) for asset in payload]
    forbidden = sorted(name for name in names if is_updater_asset(name))
    if forbidden:
        fail("unsigned release contains updater assets: " + ", ".join(forbidden))
    internal_cli = sorted(name for name in names if CLI_ASSET_RE.search(name))
    if internal_cli:
        fail(
            "unsigned release contains internal CLI assets: "
            + ", ".join(internal_cli)
        )

    selected = selected_platforms(platforms)
    desktop = {
        "windows-x64": (
            ("Windows x64 installer", ("windows-x64", "setup"), ".exe"),
            ("Windows x64 portable", ("windows-x64", "portable"), ".exe"),
        ),
        "windows-arm64": (
            ("Windows ARM64 installer", ("windows-arm64", "setup"), ".exe"),
            ("Windows ARM64 portable", ("windows-arm64", "portable"), ".exe"),
        ),
        "linux-x64": (
            ("Linux x64 DEB", ("linux-amd64",), ".deb"),
            ("Linux x64 AppImage", ("linux-amd64",), ".appimage"),
        ),
        "linux-arm64": (
            ("Linux ARM64 DEB", ("linux-arm64",), ".deb"),
            ("Linux ARM64 AppImage", ("linux-arm64",), ".appimage"),
        ),
        "macos-x64": (
            ("macOS Intel DMG", ("darwin-x64",), ".dmg"),
            ("macOS Intel APP ZIP", ("darwin-x64",), ".zip"),
        ),
        "macos-arm64": (
            ("macOS Apple Silicon DMG", ("darwin-aarch64",), ".dmg"),
            ("macOS Apple Silicon APP ZIP", ("darwin-aarch64",), ".zip"),
        ),
    }
    for platform, requirements in desktop.items():
        if platform in selected:
            for label, needles, suffix in requirements:
                require_asset(names, label, *needles, suffix=suffix)
    if "android" in selected:
        require_asset(names, "Android arm64-v8a", "arm64-v8a", suffix=".apk")
        require_asset(names, "Android armeabi-v7a", "armeabi-v7a", suffix=".apk")
        require_asset(names, "Android x86_64", "android", "x86_64", suffix=".apk")
        require_asset(names, "Android universal", "android-universal", suffix=".apk")
        require_asset(names, "Android AAB", "android", suffix=".aab")
    if "ios" in selected:
        require_asset(names, "iOS IPA", suffix=".ipa")

    installers = [
        name
        for name in names
        if name.lower().endswith(INSTALLER_SUFFIXES)
        or (
            name.lower().endswith(".zip")
            and (
                "darwin-x64" in name.lower()
                or "darwin-aarch64" in name.lower()
            )
        )
    ]
    if not installers:
        fail("unsigned release has no downloadable installer")
    return payload, installers


def write_manifest(assets: list[dict], path: Path) -> None:
    lines = []
    for asset in sorted(assets, key=lambda item: str(item["name"])):
        match = DIGEST_RE.fullmatch(str(asset.get("digest") or ""))
        if match is None:
            fail(f"invalid digest for {asset.get('name')}")
        lines.append(f"{match.group(1)}  {asset['name']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_manifest_asset(release: dict, path: Path) -> None:
    expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    matches = [
        asset
        for asset in release.get("assets", [])
        if str(asset.get("name") or "").lower() == MANIFEST_NAME.lower()
    ]
    if len(matches) != 1:
        fail("published release does not contain exactly one unsigned manifest")
    if matches[0].get("digest") != expected:
        fail("published unsigned manifest digest does not match local content")


def normalized_highlights(path: Path | None) -> list[str]:
    if path is None:
        return []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read release highlights {path}: {error}")
    lines = []
    for raw in raw_lines:
        value = raw.strip()
        if not value:
            continue
        lines.append(
            value
            if re.match(r"(?:[-*#>] |\d+[.)] )", value)
            else f"- {value}"
        )
    return lines


def public_url(repo: str, tag: str, name: str) -> str:
    return (
        f"https://github.com/{repo}/releases/download/"
        f"{quote(tag, safe='')}/{quote(name, safe='')}"
    )


def generate_notes(
    *,
    repo: str,
    tag: str,
    version: str,
    source_ref: str,
    source_commit: str,
    platforms: str,
    stable_tag: str,
    installers: list[str],
    mode: str,
    highlights: list[str],
) -> str:
    formal = mode == "formal"
    title = (
        f"番茄小说下载器未签名版 {version}"
        if formal
        else f"番茄小说下载器未签名测试版 {version}"
    )
    warning = (
        "> **未签名版本，不支持自动更新。**"
        if formal
        else "> **未签名版本，仅供测试，不支持自动更新。**"
    )
    channel = (
        "这是普通 GitHub Release（非 prerelease），但不会被标记为稳定更新来源；"
        "不会生成、上传或修改 `latest.json`。"
        if formal
        else "这是独立的 GitHub prerelease，不会替代稳定版，也不会生成、上传或修改 `latest.json`。"
    )
    lines = [
        f"## {title}",
        "",
        warning,
        "",
        f"{channel} 请从本页 Assets 手动下载，并在安装前核对 SHA-256。",
        "",
        "## 下载与校验",
        "",
        f"- [SHA-256 校验清单]({public_url(repo, tag, MANIFEST_NAME)})",
        "- 其余安装包请在本页 Assets 中按操作系统和 CPU 架构选择。",
    ]
    if highlights:
        lines += ["", "## 本次修复", "", *highlights]

    selected = selected_platforms(platforms)
    lines += ["", "## 安装限制", ""]
    if any(value.startswith("windows-") for value in selected):
        lines.append(
            "- **Windows**：安装包没有 Authenticode 签名，系统显示“未知发布者”或 SmartScreen 警告属于预期；核对 SHA-256 后再手动运行。"
        )
    if any(value.startswith("macos-") for value in selected):
        lines.append(
            "- **macOS**：APP 未经 Developer ID 签名或 Apple 公证，首次打开会触发 Gatekeeper；请在“系统设置 → 隐私与安全性”中确认“仍要打开”，不要全局关闭 Gatekeeper。"
        )
    if any(value.startswith("linux-") for value in selected):
        lines.append(
            "- **Linux**：DEB / AppImage 不带项目级发行商签名；AppImage 需要手动添加执行权限。"
        )
    if "android" in selected:
        lines.append(
            "- **Android**：APK/AAB 使用本次 CI 生成的一次性测试证书以保证可安装；不同运行的证书不一致，升级前可能需要卸载旧测试版。"
        )
    if "ios" in selected:
        lines.append(
            "- **iOS**：IPA 未经 Apple 签名，只能使用 AltStore、Sideloadly 或 TrollStore 等工具侧载。"
        )
    lines += [
        "- **自动更新**：本版本没有 updater 签名和 `latest.json`，只能手动下载覆盖安装。",
        "",
        "## 构建信息",
        "",
        f"- Tag：`{tag}`",
        f"- 源码引用：`{source_ref}`",
        f"- 源码提交：`{source_commit}`",
        f"- 构建平台：{platforms}",
        f"- 当前稳定更新通道保持为：`{stable_tag or '尚无稳定版'}`",
        f"- 可下载安装包数量：{len(installers)}",
        "",
    ]
    return "\n".join(lines)


def verify_published_urls(release: dict, repo: str, tag: str) -> None:
    prefix = f"https://github.com/{repo}/releases/download/{quote(tag, safe='')}/"
    for asset in release.get("assets", []):
        if not isinstance(asset, dict):
            fail("published release contains a malformed asset")
        name = str(asset.get("name") or "")
        expected = prefix + quote(name, safe="")
        actual = str(asset.get("browser_download_url") or "")
        if actual != expected:
            fail(f"published asset URL is not canonical for {name!r}: {actual!r}")


def publish_release(
    *,
    repo: str,
    database_id: int,
    tag: str,
    title: str,
    notes: str,
    mode: str,
) -> None:
    if mode == "prerelease":
        notes_path = Path("release-notes.md").resolve()
        notes_path.write_text(notes, encoding="utf-8")
        run(
            [
                "gh",
                "release",
                "edit",
                tag,
                "--repo",
                repo,
                "--title",
                title,
                "--notes-file",
                str(notes_path),
                "--draft=false",
                "--prerelease",
            ]
        )
        return

    payload = json.dumps(
        {
            "name": title,
            "body": notes,
            "draft": False,
            "prerelease": False,
            "make_latest": False,
        },
        ensure_ascii=False,
    )
    published = gh_json(
        [
            "api",
            "--method",
            "PATCH",
            f"repos/{repo}/releases/{database_id}",
            "--input",
            "-",
        ],
        input_text=payload,
    )
    if not isinstance(published, dict) or published.get("draft") or published.get(
        "prerelease"
    ):
        fail("GitHub did not publish the unsigned formal release")


def append_summary(
    *, repo: str, tag: str, release: dict, source_commit: str, stable_tag: str
) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not path:
        return
    with Path(path).open("a", encoding="utf-8", newline="\n") as output:
        output.write(
            "## Unsigned Tauri Release\n\n"
            f"- Release: [{tag}](https://github.com/{repo}/releases/tag/{tag})\n"
            f"- Source commit: `{source_commit}`\n"
            f"- Assets: `{len(release.get('assets', []))}`\n"
            f"- Prerelease: `{str(bool(release.get('prerelease'))).lower()}`\n"
            "- Updater metadata: `false`\n"
            f"- Stable latest preserved: `{stable_tag or 'none'}`\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--mode", choices=("prerelease", "formal"), required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--platforms", default="")
    parser.add_argument("--highlights-file", type=Path)
    parser.add_argument(
        "--work-dir", type=Path, default=Path("unsigned-release-check")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.strip().strip("/")
    tag = args.tag.strip()
    if not re.fullmatch(r"[^/]+/[^/]+", repo):
        fail(f"invalid GitHub repository: {repo!r}")
    if not re.fullmatch(r"unsigned-v[^/]+-r[1-9][0-9]*", tag):
        fail(f"invalid isolated unsigned release tag: {tag!r}")
    if not os.environ.get("GH_TOKEN"):
        fail("GH_TOKEN is required")

    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    release_path = work_dir / "release.json"
    manifest_path = work_dir / MANIFEST_NAME

    database_id = release_id(repo, tag)
    stable_before = latest_tag(repo)
    release = fetch_release(repo, database_id, release_path)
    if release.get("tag_name") != tag:
        fail(f"unexpected release tag: {release.get('tag_name')!r}")
    if release.get("draft") is not True:
        fail("unsigned assets must be finalized while the release is a draft")
    expected_prerelease = args.mode == "prerelease"
    if bool(release.get("prerelease")) != expected_prerelease:
        fail("unsigned release prerelease state does not match finalizer mode")

    version = version_field(args.version, release, tag)
    source_ref = release_field(args.source_ref, release, "源码引用")
    source_commit = release_field(args.source_commit, release, "源码提交")
    platforms = release_field(args.platforms, release, "计划平台")
    assets, installers = validate_assets(release, platforms)
    write_manifest(assets, manifest_path)
    notes = generate_notes(
        repo=repo,
        tag=tag,
        version=version,
        source_ref=source_ref,
        source_commit=source_commit,
        platforms=platforms,
        stable_tag=stable_before,
        installers=installers,
        mode=args.mode,
        highlights=normalized_highlights(args.highlights_file),
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
    validate_assets(release, platforms)
    title = (
        f"番茄小说下载器 未签名版 {version}"
        if args.mode == "formal"
        else f"番茄小说下载器 未签名测试版 {version}"
    )
    publish_release(
        repo=repo,
        database_id=database_id,
        tag=tag,
        title=title,
        notes=notes,
        mode=args.mode,
    )

    published = fetch_release(repo, database_id, release_path)
    if published.get("draft") is not False:
        fail("unsigned release is still a draft after publication")
    if bool(published.get("prerelease")) != expected_prerelease:
        fail("unsigned release changed prerelease state during publication")
    validate_assets(published, platforms)
    verify_manifest_asset(published, manifest_path)
    verify_published_urls(published, repo, tag)
    if source_commit not in str(published.get("body") or ""):
        fail("published release notes do not contain the source commit")
    stable_after = latest_tag(repo)
    if stable_after != stable_before:
        fail(
            "stable latest changed while publishing unsigned release: "
            f"{stable_before!r} -> {stable_after!r}"
        )
    append_summary(
        repo=repo,
        tag=tag,
        release=published,
        source_commit=source_commit,
        stable_tag=stable_after,
    )
    print(
        f"Unsigned release finalized: https://github.com/{repo}/releases/tag/{tag} "
        f"({len(published.get('assets', []))} assets)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
