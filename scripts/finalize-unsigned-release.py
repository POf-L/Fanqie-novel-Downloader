#!/usr/bin/env python3
"""Validate and publish an unsigned draft GitHub Release."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote


MANIFEST_NAME = "SHA256SUMS-unsigned.txt"
DRAFT_START = "<!-- fanqie:unsigned-draft:start -->"
DRAFT_END = "<!-- fanqie:unsigned-draft:end -->"
FINALIZER_START = "<!-- fanqie:unsigned-finalizer:start -->"
FINALIZER_END = "<!-- fanqie:unsigned-finalizer:end -->"
LEGACY_DRAFT_STATUS = "> ⏳ **本版本正在构建中**。"
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


def wait_for_latest_tag(
    repo: str,
    expected_tag: str,
    *,
    attempts: int = 5,
    delay_seconds: float = 2,
) -> str:
    """Allow GitHub's latest-release projection a bounded propagation window."""
    if attempts < 1:
        fail("GitHub Latest verification needs at least one attempt")
    observed = ""
    for attempt in range(1, attempts + 1):
        observed = latest_tag(repo)
        if observed == expected_tag:
            return observed
        if attempt < attempts:
            print(
                f"GitHub Latest is still {observed or '<none>'}; "
                f"waiting before retry {attempt + 1}/{attempts}",
                flush=True,
            )
            time.sleep(delay_seconds)
    fail(
        "formal unsigned release did not become GitHub Latest: "
        f"expected {expected_tag!r}, got {observed!r}"
    )


def stable_source_tag(repo: str, alias_tag: str = "stable") -> str:
    """Return the signed source named by the managed stable alias."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/releases/tags/{alias_tag}"],
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
        fail(f"GitHub stable alias API returned invalid JSON: {error}")
    if not isinstance(payload, dict):
        return ""
    if payload.get("draft") is not False or payload.get("prerelease") is not True:
        fail("stable alias must be a published prerelease")
    assets = payload.get("assets")
    if not isinstance(assets, list) or not any(
        isinstance(asset, dict) and asset.get("name") == "latest.json"
        for asset in assets
    ):
        fail("stable alias has no latest.json metadata asset")
    body = str(payload.get("body") or "")
    match = re.search(r"稳定源 Release：`([^`]+)`", body)
    if not match:
        fail("stable alias notes do not identify a signed source release")
    source_tag = match.group(1).strip()
    if not re.fullmatch(r"v[^/]+", source_tag):
        fail(f"stable alias points to an invalid source tag: {source_tag!r}")
    return source_tag


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


def has_updater_metadata(release: dict) -> bool:
    assets = release.get("assets")
    if not isinstance(assets, list):
        return False
    names = {
        str(asset.get("name") or "").lower()
        for asset in assets
        if isinstance(asset, dict)
    }
    return "latest.json" in names and any(name.endswith(".sig") for name in names)


def validate_updater_metadata(release: dict) -> None:
    if not has_updater_metadata(release):
        fail("unsigned release updater metadata is incomplete")
    names = {
        str(asset.get("name") or "")
        for asset in release.get("assets", [])
        if isinstance(asset, dict)
    }
    signatures = [name for name in names if name.lower().endswith(".sig")]
    for signature in signatures:
        if signature[:-4] not in names:
            fail(f"updater signature has no matching payload asset: {signature}")

    metadata_asset = next(
        (
            asset
            for asset in release.get("assets", [])
            if isinstance(asset, dict)
            and str(asset.get("name") or "").lower() == "latest.json"
        ),
        None,
    )
    if metadata_asset is None:
        fail("unsigned release updater metadata is incomplete")


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


def require_asset_alias(
    names: list[str],
    label: str,
    *,
    common: tuple[str, ...],
    aliases: tuple[str, ...],
    suffix: str,
) -> None:
    matches = [
        name
        for name in names
        if all(needle.lower() in name.lower() for needle in common)
        and any(alias.lower() in name.lower() for alias in aliases)
        and name.lower().endswith(suffix.lower())
    ]
    if not matches:
        fail(f"unsigned release is missing the {label} asset")


def selected_platforms(value: str) -> set[str]:
    selected = {item.strip().lower() for item in value.split(",") if item.strip()}
    if not selected:
        fail("release does not identify any build platform")
    return selected


def validate_assets(
    release: dict, platforms: str, *, allow_updater: bool = False
) -> tuple[list[dict], list[str]]:
    payload = payload_assets(release)
    names = [str(asset["name"]) for asset in payload]
    forbidden = sorted(
        name for name in names if is_updater_asset(name) and not allow_updater
    )
    if forbidden:
        fail("unsigned release contains updater assets: " + ", ".join(forbidden))
    if allow_updater:
        validate_updater_metadata(release)
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
                if label == "Linux ARM64 AppImage":
                    require_asset_alias(
                        names,
                        label,
                        common=("linux",),
                        aliases=("arm64", "aarch64"),
                        suffix=suffix,
                    )
                else:
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


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


def existing_manifest_is_current(release: dict, assets: list[dict]) -> bool:
    """Check whether a prior finalizer run already uploaded this manifest."""

    manifest_asset = next(
        (
            asset
            for asset in release.get("assets", [])
            if isinstance(asset, dict)
            and str(asset.get("name") or "").lower() == MANIFEST_NAME.lower()
        ),
        None,
    )
    if manifest_asset is None:
        return False
    expected_lines = []
    for asset in sorted(assets, key=lambda item: str(item["name"])):
        match = DIGEST_RE.fullmatch(str(asset.get("digest") or ""))
        if match is None:
            fail(f"invalid digest for {asset.get('name')}")
        expected_lines.append(f"{match.group(1)}  {asset['name']}")
    expected = ("\n".join(expected_lines) + "\n").encode("utf-8")
    actual_digest = str(manifest_asset.get("digest") or "")
    return actual_digest == "sha256:" + hashlib.sha256(expected).hexdigest()


def normalize_unsigned_updater_metadata(
    *, repo: str, tag: str, release: dict, work_dir: Path
) -> bool:
    """Normalize Tauri's draft URLs before the manifest is generated."""
    if not has_updater_metadata(release):
        return False
    metadata_path = work_dir / "latest.json"
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
    normalizer = Path(__file__).with_name("normalize-updater-metadata.py")
    run(
        [
            sys.executable,
            str(normalizer),
            "--metadata",
            str(metadata_path),
            "--assets",
            str(work_dir / "release.json"),
            "--repo",
            repo,
            "--tag",
            tag,
        ]
    )
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
    return True


def verify_device_guide(
    notes: str,
    *,
    platforms: str,
    updater_available: bool,
    mode: str = "formal",
) -> None:
    """Make the user-facing device guide a publication invariant."""

    required = [
        FINALIZER_START,
        FINALIZER_END,
        "## 平台状态与安装限制",
        "## 下载地址",
        "### 🪟 Windows",
        "### 🍎 macOS",
        "### 🐧 Linux",
        "### 🤖 Android",
        "### 📱 iOS",
        "SHA-256 完整清单",
        "### ❓ 常见问题",
        "### 💎 支持与推广",
        "### 🔗 相关链接",
        "<summary>📦 构建信息</summary>",
    ]
    selected = selected_platforms(platforms)
    platform_requirements = {
        "windows-x64": (
            "64位（常用）",
            "便携版（无需安装）",
            "windows-x64-portable.exe",
        ),
        "windows-arm64": (
            "ARM64（Surface / 骁龙本）",
            "便携版（无需安装）",
            "windows-arm64-portable.exe",
        ),
        "linux-x64": (
            "DEB 包（推荐，体积小，Debian / Ubuntu 等）",
            "AppImage（免安装）",
            "linux-amd64.deb",
            "linux-amd64.AppImage",
        ),
        "linux-arm64": (
            "DEB 包（推荐，体积小，Debian / Ubuntu 等）",
            "AppImage（免安装）",
            "linux-arm64.deb",
        ),
        "macos-x64": (
            "Intel 芯片",
            "APP 压缩包",
            "darwin-x64.dmg",
            "darwin-x64.zip",
        ),
        "macos-arm64": (
            "Apple M 芯片",
            "APP 压缩包",
            "darwin-aarch64.dmg",
            "darwin-aarch64.zip",
        ),
        "android": (
            "64位 arm64-v8a",
            "32位 armeabi-v7a",
            "通用版 universal",
            "x86_64（模拟器 / 部分平板）",
            "AAB（上架用）",
        ),
        "ios": ("无签名 IPA（需自行侧载）",),
    }
    for platform in sorted(selected):
        requirements = platform_requirements.get(platform)
        if requirements is None:
            fail(f"unsupported platform in unsigned device guide: {platform}")
        required.extend(requirements)
    missing = [value for value in required if value not in notes]
    if "linux-arm64" in selected and not any(
        value in notes
        for value in ("linux-arm64.AppImage", "linux-aarch64.AppImage")
    ):
        missing.append("Linux ARM64 AppImage")
    if updater_available:
        required_channel_values = ("Minisign",)
        if mode != "prerelease":
            required_channel_values += ("unsigned/latest.json",)
        for value in required_channel_values:
            if value not in notes:
                missing.append(value)
    if missing:
        fail("unsigned release device guide is incomplete: " + ", ".join(missing))


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


def generate_full_notes(
    *,
    release: dict,
    repo: str,
    tag: str,
    version: str,
    source_ref: str,
    source_commit: str,
    platforms: str,
    mode: str,
    highlights: list[str],
) -> str:
    """Use the same asset-aware renderer as signed releases.

    The old unsigned finalizer had a second short template which overwrote the
    draft's device/architecture guide.  Loading the shared renderer here keeps
    the published body in sync with the actual assets.
    """
    preparer_path = Path(__file__).with_name("prepare-release-artifacts.py")
    spec = importlib.util.spec_from_file_location(
        "fanqie_prepare_release_artifacts", preparer_path
    )
    if spec is None or spec.loader is None:
        fail(f"cannot load shared release notes renderer: {preparer_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate_notes(
        release,
        repo=repo,
        tag=tag,
        version=version,
        source_ref=source_ref,
        source_commit=source_commit,
        platforms=platforms,
        highlights=highlights,
        channel="unsigned",
        manifest_name=MANIFEST_NAME,
        updater_available=has_updater_metadata(release),
    )


def generate_finalizer_appendix(
    *,
    release: dict,
    repo: str,
    tag: str,
    version: str,
    source_ref: str,
    source_commit: str,
    platforms: str,
    mode: str,
    highlights: list[str],
) -> str:
    rendered = generate_full_notes(
        release=release,
        repo=repo,
        tag=tag,
        version=version,
        source_ref=source_ref,
        source_commit=source_commit,
        platforms=platforms,
        mode=mode,
        highlights=highlights,
    )
    guide_start = rendered.find("## 平台状态与安装限制")
    details_separator = "\n---\n\n### ❓ 常见问题"
    guide_end = rendered.find(details_separator, guide_start)
    if guide_start < 0 or guide_end < 0:
        fail("shared release renderer did not produce the device guide")
    device_guide = rendered[guide_start:guide_end].rstrip()
    details = rendered[guide_end + len("\n---\n\n") :].rstrip()
    highlights_start = rendered.find("## 本次修复")
    highlights_section = (
        rendered[highlights_start:guide_start].rstrip()
        if 0 <= highlights_start < guide_start
        else ""
    )
    updater_available = has_updater_metadata(release)
    update_line = (
        (
            f"- 无签名自动更新元数据：[latest.json]({public_url(repo, tag, 'latest.json')})；"
            "客户端通过固定 `unsigned/latest.json` 别名读取，并使用项目 updater 公钥验签。"
        )
        if updater_available and mode != "prerelease"
        else (
            f"- 测试预发布 updater 元数据：[latest.json]({public_url(repo, tag, 'latest.json')})；"
            "该版本不进入固定 `unsigned` 别名，只有显式安装测试通道的客户端会读取并验签。"
            if updater_available
            else "- 这个历史版本没有 updater 元数据，只能手动覆盖安装。"
        )
    )
    validate_assets(release, platforms, allow_updater=updater_available)
    parts = [
        FINALIZER_START,
        "---",
        "",
        "## 无签名 Release Finalizer",
        "",
        "> 构建与附件校验已经完成。以下设备/架构链接由无签名专用 finalizer "
        "根据本 Release 的实际 Assets 追加生成；下载时以本区块为准。",
        "",
    ]
    if highlights_section:
        parts.extend([highlights_section, ""])
    parts.extend(
        [
            device_guide,
            "",
            "## 校验与更新通道",
            "",
            f"- [SHA-256 完整清单]({public_url(repo, tag, MANIFEST_NAME)})",
            update_line,
            "- 无签名指 Windows Authenticode、macOS Developer ID/公证和 iOS Apple 签名；"
            "若提供 updater 元数据，更新包本身仍必须通过独立的 Minisign 签名校验。",
            "",
            "---",
            "",
            details,
            "",
            FINALIZER_END,
        ]
    )
    appendix = "\n".join(parts)
    verify_device_guide(
        appendix,
        platforms=platforms,
        updater_available=updater_available,
        mode=mode,
    )
    return appendix


def managed_block_bounds(
    body: str, start_marker: str, end_marker: str, label: str
) -> tuple[int, int] | None:
    starts = body.count(start_marker)
    ends = body.count(end_marker)
    if starts != ends or starts > 1:
        fail(f"release body contains invalid {label} markers")
    if starts == 0:
        return None
    start = body.find(start_marker)
    end = body.find(end_marker, start + len(start_marker))
    if end < start:
        fail(f"release body contains an incomplete {label} block")
    return start, end + len(end_marker)


def strip_legacy_draft(body: str) -> str:
    """Remove only the fully recognized pre-marker unsigned Draft template."""

    occurrences = body.count(LEGACY_DRAFT_STATUS)
    if occurrences == 0:
        return body
    if occurrences != 1:
        fail("legacy unsigned Draft status is ambiguous")
    start = body.find(LEGACY_DRAFT_STATUS)
    build_anchor = body.find("- 正在构建版本：", start)
    close = body.find("</details>", build_anchor)
    finalizer = body.find(FINALIZER_START, start)
    if build_anchor < 0 or close < 0 or (finalizer >= 0 and close > finalizer):
        fail("legacy unsigned Draft boundary is incomplete")
    legacy = body[start : close + len("</details>")]
    sentinels = (
        "下方下载链接**暂时指向最新已发布版本**",
        "## 下载地址（默认：最新已发布版本）",
        "### 💎 支持与推广",
        "- 计划平台：",
    )
    missing = [sentinel for sentinel in sentinels if sentinel not in legacy]
    if missing:
        fail("legacy unsigned Draft template is not recognized: " + ", ".join(missing))
    return body[:start] + body[close + len("</details>") :]


def clean_draft_body(body: str, *, allow_legacy: bool = False) -> str:
    bounds = managed_block_bounds(body, DRAFT_START, DRAFT_END, "unsigned Draft")
    if bounds is not None:
        body = body[: bounds[0]] + body[bounds[1] :]
    if LEGACY_DRAFT_STATUS in body:
        if not allow_legacy:
            fail("legacy unsigned Draft cleanup requires an explicit maintenance operation")
        body = strip_legacy_draft(body)
    return body


def merge_unsigned_draft(existing: str, generated: str) -> str:
    """Refresh only the managed Draft block while preserving user-authored text."""

    if FINALIZER_START in existing or FINALIZER_END in existing:
        fail("cannot merge Draft notes into an already finalized Release")
    generated_bounds = managed_block_bounds(
        generated, DRAFT_START, DRAFT_END, "generated unsigned Draft"
    )
    if generated_bounds is None:
        fail("generated unsigned Draft has no managed block")
    generated_block = generated[generated_bounds[0] : generated_bounds[1]]
    existing_bounds = managed_block_bounds(
        existing, DRAFT_START, DRAFT_END, "unsigned Draft"
    )
    if existing_bounds is not None:
        return (
            existing[: existing_bounds[0]]
            + generated_block
            + existing[existing_bounds[1] :]
        )
    if LEGACY_DRAFT_STATUS in existing:
        fail("legacy unsigned Draft cleanup requires an explicit maintenance operation")
    if not existing.strip():
        return generated
    separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return f"{existing}{separator}{generated_block}\n"


def append_finalizer(
    body: str, appendix: str, *, allow_legacy_draft: bool = False
) -> str:
    """Remove managed Draft state and append or refresh the finalizer block."""

    body = clean_draft_body(body, allow_legacy=allow_legacy_draft)
    starts = body.count(FINALIZER_START)
    ends = body.count(FINALIZER_END)
    if starts != ends or starts > 1:
        fail("release body contains invalid unsigned finalizer markers")
    if starts == 1:
        start = body.find(FINALIZER_START)
        end = body.find(FINALIZER_END, start + len(FINALIZER_START))
        if end < start:
            fail("release body contains an incomplete unsigned finalizer block")
        end += len(FINALIZER_END)
        return body[:start] + appendix.rstrip() + body[end:]
    if not body:
        return f"{appendix.rstrip()}\n"
    separator = (
        "" if body.endswith("\n\n") else ("\n" if body.endswith("\n") else "\n\n")
    )
    return f"{body}{separator}{appendix.rstrip()}\n"


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
            # GitHub's REST release API declares make_latest as a string
            # enum ("true", "false", or "legacy"), not a JSON boolean.
            "make_latest": "true",
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
            f"- Updater metadata: `{str(has_updater_metadata(release)).lower()}`\n"
            f"- Stable source preserved: `{stable_tag or 'none'}`\n"
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
    parser.add_argument("--allow-legacy-draft", action="store_true")
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
    release = fetch_release(repo, database_id, release_path)
    if release.get("tag_name") != tag:
        fail(f"unexpected release tag: {release.get('tag_name')!r}")
    resume_published = release.get("draft") is False
    if release.get("draft") not in (True, False):
        fail("unsigned release has an invalid draft state")
    expected_prerelease = args.mode == "prerelease"
    if bool(release.get("prerelease")) != expected_prerelease:
        fail("unsigned release prerelease state does not match finalizer mode")
    already_finalized = False
    if resume_published:
        body = str(release.get("body") or "")
        asset_names = {
            str(asset.get("name") or "")
            for asset in release.get("assets", [])
            if isinstance(asset, dict)
        }
        already_finalized = FINALIZER_START in body or MANIFEST_NAME in asset_names
        if already_finalized:
            if body.count(FINALIZER_START) != 1 or body.count(FINALIZER_END) != 1:
                fail("published unsigned release has invalid finalizer markers")
            if MANIFEST_NAME not in asset_names:
                fail("published unsigned release has no finalizer manifest")
            print(
                "Resuming unsigned channel publication after finalizer completion",
                flush=True,
            )
        else:
            print(
                "Resuming an unsigned release published before finalizer completion",
                flush=True,
            )

    stable_before = stable_source_tag(repo)
    if not stable_before:
        stable_publisher = Path(__file__).with_name("publish-stable-channel.py")
        stable_dir = Path(os.environ.get("RUNNER_TEMP", str(work_dir.parent))) / (
            "stable-channel-check"
        )
        run(
            [
                sys.executable,
                str(stable_publisher),
                "--repo",
                repo,
                "--work-dir",
                str(stable_dir),
            ]
        )
        stable_before = stable_source_tag(repo)
        if not stable_before:
            fail("stable updater channel could not be initialized")

    version = version_field(args.version, release, tag)
    source_ref = release_field(args.source_ref, release, "源码引用")
    source_commit = release_field(args.source_commit, release, "源码提交")
    platforms = release_field(args.platforms, release, "计划平台")
    updater_available = normalize_unsigned_updater_metadata(
        repo=repo,
        tag=tag,
        release=release,
        work_dir=work_dir,
    )
    if updater_available:
        release = fetch_release(repo, database_id, release_path)
    assets, installers = validate_assets(
        release, platforms, allow_updater=updater_available
    )
    if already_finalized:
        if not existing_manifest_is_current(release, assets):
            fail("published unsigned manifest no longer matches release assets")
        verify_device_guide(
            str(release.get("body") or ""),
            platforms=platforms,
            updater_available=updater_available,
            mode=args.mode,
        )
        observed_latest = wait_for_latest_tag(repo, tag) if args.mode == "formal" else ""
        if updater_available and args.mode == "formal":
            unsigned_publisher = Path(__file__).with_name(
                "publish-unsigned-channel.py"
            )
            unsigned_dir = Path(
                os.environ.get("RUNNER_TEMP", str(work_dir.parent))
            ) / "unsigned-channel-check"
            run(
                [
                    sys.executable,
                    str(unsigned_publisher),
                    "--repo",
                    repo,
                    "--source-tag",
                    tag,
                    "--work-dir",
                    str(unsigned_dir),
                ]
            )
        stable_after = stable_source_tag(repo)
        if stable_after != stable_before:
            fail(
                "stable channel changed while resuming unsigned release: "
                f"{stable_before!r} -> {stable_after!r}"
            )
        append_summary(
            repo=repo,
            tag=tag,
            release=release,
            source_commit=source_commit,
            stable_tag=stable_after,
        )
        print(
            f"Unsigned release finalizer resumed: "
            f"https://github.com/{repo}/releases/tag/{tag}",
            flush=True,
        )
        return 0
    write_manifest(assets, manifest_path)
    appendix = generate_finalizer_appendix(
        release=release,
        repo=repo,
        tag=tag,
        version=version,
        source_ref=source_ref,
        source_commit=source_commit,
        platforms=platforms,
        mode=args.mode,
        highlights=normalized_highlights(args.highlights_file),
    )
    notes = append_finalizer(
        str(release.get("body") or ""),
        appendix,
        allow_legacy_draft=args.allow_legacy_draft,
    )
    verify_device_guide(
        notes,
        platforms=platforms,
        updater_available=updater_available,
        mode=args.mode,
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
    validate_assets(release, platforms, allow_updater=updater_available)
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
    validate_assets(published, platforms, allow_updater=updater_available)
    verify_manifest_asset(published, manifest_path)
    verify_published_urls(published, repo, tag)
    if source_commit not in str(published.get("body") or ""):
        fail("published release notes do not contain the source commit")
    verify_device_guide(
        str(published.get("body") or ""),
        platforms=platforms,
        updater_available=updater_available,
        mode=args.mode,
    )
    observed_latest = wait_for_latest_tag(repo, tag) if args.mode == "formal" else ""
    if updater_available and args.mode == "formal":
        unsigned_publisher = Path(__file__).with_name("publish-unsigned-channel.py")
        unsigned_dir = Path(os.environ.get("RUNNER_TEMP", str(work_dir.parent))) / (
            "unsigned-channel-check"
        )
        run(
            [
                sys.executable,
                str(unsigned_publisher),
                "--repo",
                repo,
                "--source-tag",
                tag,
                "--work-dir",
                str(unsigned_dir),
            ]
        )
    stable_after = stable_source_tag(repo)
    if stable_after != stable_before:
        fail(
            "stable channel changed while publishing unsigned release: "
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
