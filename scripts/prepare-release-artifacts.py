#!/usr/bin/env python3
"""Generate and verify release notes and the full SHA-256 manifest."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import quote


MANIFEST_NAME = "SHA256SUMS-release.txt"
CONTROL_ASSETS = {
    "ABIS.txt",
    "latest.json",
    MANIFEST_NAME,
    "SHA256SUMS-android.txt",
    "SHA256SUMS-ios.txt",
    "SIGNING.txt",
}
INSTALLER_SUFFIXES = (
    ".aab",
    ".apk",
    ".appimage",
    ".deb",
    ".dmg",
    ".exe",
    ".ipa",
    ".msi",
)
SHA256_RE = re.compile(r"sha256:([0-9a-f]{64})\Z")
MANIFEST_LINE_RE = re.compile(r"([0-9a-f]{64}) [ *](.+)\Z")


def fail(message: str) -> None:
    raise SystemExit(message)


def read_release(path: Path, tag: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read release JSON {path}: {error}")
    if not isinstance(payload, dict):
        fail("release JSON must contain an object")
    if payload.get("tag_name") != tag:
        fail(
            f"release tag mismatch: expected {tag!r}, "
            f"got {payload.get('tag_name')!r}"
        )
    if not isinstance(payload.get("assets"), list) or not payload["assets"]:
        fail("release JSON does not contain any assets")
    return payload


def assets_by_name(release: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for asset in release["assets"]:
        if not isinstance(asset, dict):
            fail("release contains a malformed asset entry")
        name = str(asset.get("name") or "").strip()
        if not name:
            fail("release contains an asset without a name")
        if "\n" in name or "\r" in name:
            fail(f"release asset has an unsafe name: {name!r}")
        if name in result:
            fail(f"release contains duplicate asset name: {name}")
        result[name] = asset
    return result


def asset_digests(release: dict) -> dict[str, str]:
    digests: dict[str, str] = {}
    for name, asset in assets_by_name(release).items():
        if name == MANIFEST_NAME:
            continue
        match = SHA256_RE.fullmatch(str(asset.get("digest") or ""))
        if match is None:
            fail(f"release asset has no valid GitHub SHA-256 digest: {name}")
        digests[name] = match.group(1)
    return digests


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as output:
            output.write(content)
            temporary = Path(output.name)
        temporary.replace(path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def write_manifest(release: dict, path: Path) -> None:
    digests = asset_digests(release)
    lines = [f"{digest}  {name}" for name, digest in sorted(digests.items())]
    atomic_write(path, "\n".join(lines) + "\n")


def parse_manifest(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read release manifest {path}: {error}")
    parsed: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        match = MANIFEST_LINE_RE.fullmatch(line)
        if match is None:
            fail(f"invalid manifest line {number}: {line!r}")
        digest, name = match.groups()
        name = name.removeprefix("./")
        if name in parsed:
            fail(f"duplicate manifest entry: {name}")
        parsed[name] = digest
    return parsed


def check_manifest(release: dict, path: Path) -> None:
    expected = asset_digests(release)
    actual = parse_manifest(path)
    if actual != expected:
        missing = sorted(expected.keys() - actual.keys())
        unexpected = sorted(actual.keys() - expected.keys())
        changed = sorted(
            name
            for name in expected.keys() & actual.keys()
            if expected[name] != actual[name]
        )
        fail(
            "release manifest does not match GitHub asset digests; "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )


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
        fail(
            f"missing {label}; pass it explicitly or retain it in the draft notes"
        )
    return value


def public_url(repo: str, tag: str, name: str) -> str:
    return (
        f"https://github.com/{repo}/releases/download/"
        f"{quote(tag, safe='')}/{quote(name, safe='')}"
    )


def links(repo: str, tag: str, names: list[str], labels: dict[str, str]) -> str:
    if not names:
        return "_本版本未提供_"
    result = []
    for name in names:
        label = name
        lowered = name.lower()
        for needle, candidate in labels.items():
            if needle in lowered:
                label = candidate
                break
        result.append(f"[{label}]({public_url(repo, tag, name)})")
    return " | ".join(result)


def normalized_highlights(path: Path | None) -> list[str]:
    if path is None:
        return []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read release highlights {path}: {error}")
    lines = []
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            continue
        if not re.match(r"(?:[-*#>] |\d+[.)] )", line):
            line = f"- {line}"
        lines.append(line)
    return lines


def platform_status_lines(
    *,
    repo: str,
    asset_names: set[str],
    win_x64: list[str],
    win_arm: list[str],
    mac_arm: list[str],
    mac_x64: list[str],
    linux_deb_x64: list[str],
    linux_deb_arm: list[str],
    linux_app_x64: list[str],
    linux_app_arm: list[str],
    android_arm64: list[str],
    android_v7: list[str],
    android_x86: list[str],
    android_universal: list[str],
    android_aab: list[str],
    ios_ipa: list[str],
    prerelease: bool,
) -> list[str]:
    """Explain install/signing limits from the assets actually published."""

    mac_assets = mac_arm + mac_x64
    mac_unsigned = any("unsigned" in name.lower() for name in mac_assets)
    android_assets = (
        android_arm64
        + android_v7
        + android_x86
        + android_universal
        + android_aab
    )
    lines = [
        "",
        "## 平台状态与安装限制",
        "",
        "以下说明以本 Release 的实际附件和当前发布门禁为准；未列出附件的平台不应从本页猜测下载地址。",
        "",
    ]

    if win_x64 or win_arm:
        lines.append(
            "- **Windows**：提供 NSIS 安装包。当前公开流水线未配置 Authenticode "
            "证书，SmartScreen 或“无法验证发行商”提示属于预期；先核对 SHA-256，"
            "再在文件属性中选择“解除锁定”。"
        )
    else:
        lines.append(
            "- **Windows**：本版本未提供安装包；不要把其他架构或旧版本当作替代品。"
        )

    if mac_unsigned:
        lines.append(
            "- **macOS**：本版本包明确标注为未签名、未公证的预发布包。按 Intel "
            "或 Apple Silicon 选择架构，首次打开请在“系统设置 → 隐私与安全性”"
            "中确认“仍要打开”；不要全局关闭 Gatekeeper，也不要依赖本包的一键更新。"
        )
    elif mac_assets:
        lines.append(
            "- **macOS**：本版本包含通过 Developer ID 签名、公证和 Gatekeeper "
            "门禁的安装包；仍应按 Intel 或 Apple Silicon 选择架构。"
        )
    else:
        lines.append(
            f"- **macOS**：本版本未提供稳定安装包。稳定渠道需要 Developer ID "
            f"签名和 Apple 公证；可在 [Releases](https://github.com/{repo}/releases) "
            "中查找单独标注的未签名 macOS 预发布包。"
        )

    if (
        linux_deb_x64
        or linux_deb_arm
        or linux_app_x64
        or linux_app_arm
    ):
        lines.append(
            "- **Linux**：DEB 和 AppImage 不提供项目级发行商签名；请按发行版和 "
            "CPU 架构选择，AppImage 需要执行权限，并先核对 SHA-256。"
        )
    else:
        lines.append("- **Linux**：本版本未提供安装包。")

    if android_assets:
        if "SIGNING.txt" in asset_names:
            lines.append(
                "- **Android**：APK/AAB 使用发布密钥签名并经 `apksigner` 验证；"
                "安装 APK 仍需在系统设置中允许该来源安装应用。"
            )
        else:
            lines.append(
                "- **Android**：本版本没有发布签名证明；正式发布在缺少 keystore "
                "时会阻止，不应安装来源不明的 unsigned APK。"
            )
    else:
        lines.append(
            "- **Android**：本版本未提供安装包；缺少发布 keystore 时不会绕过门禁发布 unsigned APK。"
        )

    if ios_ipa:
        lines.append(
            "- **iOS**：本仓库当前 IPA 按无 Apple 签名侧载模式发布，不支持 App Store；"
            "请使用 AltStore、Sideloadly 或 TrollStore，并按系统提示信任侧载环境。"
        )
    else:
        lines.append(
            "- **iOS**：本版本未提供 IPA；没有 Apple 签名和对应构建产物时不会伪装成可安装包。"
        )

    if prerelease:
        lines.append(
            "- **自动更新**：这是 prerelease，不会成为 GitHub 稳定版 `latest`；"
            "未签名或没有 updater 签名的附件请手动下载并覆盖安装。"
        )
    else:
        lines.append(
            "- **自动更新**：稳定版的一键更新只适用于带有效 updater 签名和 `latest.json` "
            "条目的桌面附件；侧载或未签名包遇到更新问题时请手动下载安装包。"
        )
    return lines


def generate_notes(
    release: dict,
    *,
    repo: str,
    tag: str,
    version: str,
    source_ref: str,
    source_commit: str,
    platforms: str,
    highlights: list[str],
) -> str:
    names = sorted(assets_by_name(release))
    installers = [
        name
        for name in names
        if name not in CONTROL_ASSETS
        and not name.lower().endswith(".sig")
        and name.lower().endswith(INSTALLER_SUFFIXES)
    ]
    if not installers:
        fail("release does not contain any downloadable installer assets")

    def pick(*needles: str, suffix: str | None = None) -> list[str]:
        result = []
        for name in installers:
            lowered = name.lower()
            if all(needle.lower() in lowered for needle in needles) and (
                suffix is None or lowered.endswith(suffix.lower())
            ):
                result.append(name)
        return result

    win_x64 = pick("windows-x64", suffix=".exe")
    win_arm = pick("windows-arm64", suffix=".exe")
    mac_arm = pick("darwin-aarch64", suffix=".dmg")
    mac_x64 = pick("darwin-x64", suffix=".dmg")
    linux_deb_x64 = pick("linux-amd64", suffix=".deb")
    linux_deb_arm = pick("linux-arm64", suffix=".deb")
    linux_app_x64 = pick("linux-amd64", suffix=".appimage")
    linux_app_arm = [
        name
        for name in installers
        if ("linux-arm64" in name.lower() or "linux-aarch64" in name.lower())
        and name.lower().endswith(".appimage")
    ]
    android_arm64 = pick("arm64-v8a", suffix=".apk")
    android_v7 = pick("armeabi-v7a", suffix=".apk")
    android_x86 = pick("x86_64", suffix=".apk")
    android_universal = pick("universal", suffix=".apk")
    android_aab = [name for name in installers if name.lower().endswith(".aab")]
    ios_ipa = [name for name in installers if name.lower().endswith(".ipa")]

    asset_names = set(names)
    shipped = []
    if win_x64 or win_arm:
        shipped.append("Windows")
    if mac_arm or mac_x64:
        shipped.append("macOS")
    if linux_deb_x64 or linux_deb_arm or linux_app_x64 or linux_app_arm:
        shipped.append("Linux")
    if (
        android_arm64
        or android_v7
        or android_x86
        or android_universal
        or android_aab
    ):
        shipped.append("Android")
    if ios_ipa:
        shipped.append("iOS（无签名 IPA）")
    shipped_text = " / ".join(shipped) if shipped else "无"

    prerelease = bool(release.get("prerelease"))
    lines = [
        f"## {version}{'（测试预发布）' if prerelease else '（正式版）'}",
        "",
        "基于 **Rust + Tauri v2** 的番茄小说下载器。",
        "",
        "> 📱 **项目目标平台**：Windows / Linux / macOS / Android / iOS。",
        f"> 📦 **本版本实际产出**：{shipped_text}。",
        "> iOS 为无签名 IPA，需自行侧载，不上架 App Store。",
    ]
    if not prerelease:
        lines.extend(
            [
                ">",
                "> 🔄 已安装旧版的用户，可直接在软件内使用「一键更新」。",
            ]
        )
    if highlights:
        lines.extend(["", "## 本次修复", "", *highlights])

    lines.extend(
        platform_status_lines(
            repo=repo,
            asset_names=asset_names,
            win_x64=win_x64,
            win_arm=win_arm,
            mac_arm=mac_arm,
            mac_x64=mac_x64,
            linux_deb_x64=linux_deb_x64,
            linux_deb_arm=linux_deb_arm,
            linux_app_x64=linux_app_x64,
            linux_app_arm=linux_app_arm,
            android_arm64=android_arm64,
            android_v7=android_v7,
            android_x86=android_x86,
            android_universal=android_universal,
            android_aab=android_aab,
            ios_ipa=ios_ipa,
            prerelease=prerelease,
        )
    )

    lines.extend(
        [
            "",
            "## 下载地址",
            "",
            "### 🪟 Windows",
            "",
            "#### 安装包（推荐）",
            "",
            f"- {links(repo, tag, win_x64, {'x64': '64位（常用）'})}",
        ]
    )
    if win_arm:
        lines.append(
            f"- {links(repo, tag, win_arm, {'arm64': 'ARM64（Surface / 骁龙本）'})}"
        )
    lines.extend(
        [
            "",
            "### 🍎 macOS",
            "",
            f"- {links(repo, tag, mac_arm, {'aarch64': 'Apple M 芯片（推荐）'})}",
            f"- {links(repo, tag, mac_x64, {'x64': 'Intel 芯片'})}",
            "",
            "### 🐧 Linux",
            "",
            "#### DEB 包（推荐，体积小，Debian / Ubuntu 等）",
            "",
            f"- {links(repo, tag, linux_deb_x64, {'amd64': '64位'})}",
        ]
    )
    if linux_deb_arm:
        lines.append(f"- {links(repo, tag, linux_deb_arm, {'arm64': 'ARM64'})}")
    lines.extend(
        [
            "",
            "#### AppImage（免安装）",
            "",
            f"- {links(repo, tag, linux_app_x64, {'amd64': '64位'})}",
        ]
    )
    if linux_app_arm:
        lines.append(
            f"- {links(repo, tag, linux_app_arm, {'arm64': 'ARM64', 'aarch64': 'ARM64'})}"
        )
    lines.extend(["", "### 🤖 Android", "", "#### 手机安装包", ""])
    if android_arm64:
        lines.append(
            f"- {links(repo, tag, android_arm64, {'arm64-v8a': '64位 arm64-v8a（现代手机，推荐）'})}"
        )
    if android_v7:
        lines.append(
            f"- {links(repo, tag, android_v7, {'armeabi-v7a': '32位 armeabi-v7a（老旧手机）'})}"
        )
    if android_universal:
        lines.append(
            f"- {links(repo, tag, android_universal, {'universal': '通用版 universal（兼容所有设备）'})}"
        )
    if android_x86:
        lines.append(
            f"- {links(repo, tag, android_x86, {'x86_64': 'x86_64（模拟器 / 部分平板）'})}"
        )
    if not (android_arm64 or android_v7 or android_universal or android_x86):
        lines.append("- _本版本未提供_")
    lines.extend(
        [
            "",
            "#### 应用商店包",
            "",
            f"- {links(repo, tag, android_aab, {'aab': 'AAB（上架用）'})}",
            "",
            "### 📱 iOS",
            "",
            f"- {links(repo, tag, ios_ipa, {'ipa': '无签名 IPA（需自行侧载）'})}",
        ]
    )
    if ios_ipa:
        lines.extend(
            [
                "",
                "> ⚠️ **未上架 App Store**。此 IPA **无 Apple 签名**，需自行用 "
                "AltStore / Sideloadly / TrollStore 等工具侧载安装。",
                "> 安装后需信任开发者证书（设置 → 通用 → VPN 与设备管理）。",
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "### ❓ 常见问题",
            "",
            "- **Windows 提示无法验证发行商**：安装包右键 → 属性 → 勾选「解除锁定」后再运行。",
            "- **Linux DEB 打不开**：先安装 `libwebkit2gtk-4.1`（Ubuntu/Debian）。",
            "- **Android 安装被拦截**：系统设置中允许「安装未知来源应用」。",
            "- **iOS 如何安装**：下载无签名 IPA，用 AltStore / Sideloadly / TrollStore 等工具侧载；不支持 App Store。",
            "- **软件内更新失败**：可手动下载本页对应平台安装包覆盖安装。",
            "",
            "### 💎 支持与推广",
            "",
            "如果这个项目对你有帮助，也欢迎支持一下合作服务：",
            "",
            "> 走邀请码注册即送 **1 美元**，不走邀请链接是没有的。麻烦各位体验一下了。",
            "",
            "- [注册链接（含邀请码）](https://999554.xyz/register?aff=Xf2p)",
            "",
            f"也诚招赞助与推广合作，可通过 [Issues](https://github.com/{repo}/issues) 留言联系。",
            "",
            "### 🔗 相关链接",
            "",
            f"- [问题反馈](https://github.com/{repo}/issues)",
            f"- [项目说明](https://github.com/{repo})",
            "",
            "<details>",
            "<summary>📦 构建信息</summary>",
            "",
            f"- 版本：`{version}`",
            f"- Tag：`{tag}`",
            f"- 类型：{'测试预发布（Pre-release）' if prerelease else '正式稳定版'}",
            f"- 源码引用：`{source_ref}`",
            f"- 源码提交：`{source_commit}`",
            f"- 构建平台：{platforms}",
            f"- 本版本实际产出：{shipped_text}",
            f"- 可下载安装包数量：{len(installers)}（不含更新签名和校验文件）",
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)


def valid_repo(value: str) -> str:
    value = value.strip().strip("/")
    if not re.fullmatch(r"[^/]+/[^/]+", value):
        fail(f"invalid GitHub repository: {value!r}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--repo", type=valid_repo, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", default="")
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--platforms", default="")
    parser.add_argument("--highlights-file", type=Path)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.tag.strip() or "/" in args.tag:
        fail(f"invalid GitHub release tag: {args.tag!r}")
    release = read_release(args.release, args.tag)
    if args.check:
        check_manifest(release, args.manifest)
        print(
            f"Release manifest verified: {len(asset_digests(release))} assets"
        )
        return 0

    if args.notes is None:
        fail("--notes is required unless --check is used")
    source_ref = release_field(args.source_ref, release, "源码引用")
    source_commit = release_field(args.source_commit, release, "源码提交")
    platforms = release_field(args.platforms, release, "计划平台")
    version = args.version.strip() or args.tag.removeprefix("v")
    write_manifest(release, args.manifest)
    notes = generate_notes(
        release,
        repo=args.repo,
        tag=args.tag,
        version=version,
        source_ref=source_ref,
        source_commit=source_commit,
        platforms=platforms,
        highlights=normalized_highlights(args.highlights_file),
    )
    atomic_write(args.notes, notes)
    print(
        f"Prepared release notes and manifest for {len(asset_digests(release))} assets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
