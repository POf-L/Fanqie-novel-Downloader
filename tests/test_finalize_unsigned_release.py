import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finalize-unsigned-release.py"
SPEC = importlib.util.spec_from_file_location("finalize_unsigned_release", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FinalizeUnsignedReleaseTest(unittest.TestCase):
    def fixture(self):
        names = [
            "FanqieNovelDownloader-tauri-windows-x64-setup.exe",
            "FanqieNovelDownloader-tauri-windows-x64-portable.exe",
            "FanqieNovelDownloader-tauri-windows-arm64-setup.exe",
            "FanqieNovelDownloader-tauri-windows-arm64-portable.exe",
            "FanqieNovelDownloader-tauri-linux-amd64.deb",
            "FanqieNovelDownloader-tauri-linux-amd64.AppImage",
            "FanqieNovelDownloader-tauri-linux-arm64.deb",
            "FanqieNovelDownloader-tauri-linux-aarch64.AppImage",
            "FanqieNovelDownloader-tauri-darwin-x64.dmg",
            "FanqieNovelDownloader-tauri-darwin-x64.zip",
            "FanqieNovelDownloader-tauri-darwin-aarch64.dmg",
            "FanqieNovelDownloader-tauri-darwin-aarch64.zip",
            "FanqieNovelDownloader-android-arm64-v8a.apk",
            "FanqieNovelDownloader-android-armeabi-v7a.apk",
            "FanqieNovelDownloader-android-x86_64.apk",
            "FanqieNovelDownloader-android-universal.apk",
            "FanqieNovelDownloader-android.aab",
            "FanqieNovelDownloader.ipa",
        ]
        return {
            "assets": [
                {"name": name, "digest": "sha256:" + "0" * 64}
                for name in names
            ]
        }

    def test_full_platform_asset_set_passes_without_updater_files(self):
        platforms = (
            "windows-x64, windows-arm64, linux-x64, linux-arm64, "
            "macos-x64, macos-arm64, android, ios"
        )
        assets, installers = MODULE.validate_assets(self.fixture(), platforms)
        self.assertEqual(len(assets), 18)
        self.assertEqual(len(installers), 18)

    def test_updater_metadata_is_rejected(self):
        release = self.fixture()
        release["assets"].append(
            {"name": "latest.json", "digest": "sha256:" + "1" * 64}
        )
        with self.assertRaisesRegex(SystemExit, "contains updater assets"):
            MODULE.validate_assets(release, "windows-x64")

    def test_unsigned_finalizer_reports_real_updater_availability(self):
        platforms = (
            "windows-x64, windows-arm64, linux-x64, linux-arm64, "
            "macos-x64, macos-arm64, android, ios"
        )
        historical = self.fixture()
        historical["prerelease"] = False
        historical_notes = MODULE.generate_finalizer_appendix(
            release=historical,
            repo="POf-L/Fanqie-novel-Downloader",
            tag="unsigned-v2099.1.1-r1",
            version="2099.1.1",
            source_ref="main",
            source_commit="0123456789ab",
            platforms=platforms,
            mode="formal",
            highlights=[],
        )
        self.assertIn("历史版本没有 updater 元数据", historical_notes)

        updatable = self.fixture()
        updatable["prerelease"] = False
        updatable["assets"].extend(
            [
                {"name": "latest.json", "digest": "sha256:" + "1" * 64},
                {
                    "name": "FanqieNovelDownloader-tauri-windows-x64-setup.exe.sig",
                    "digest": "sha256:" + "2" * 64,
                },
            ]
        )
        updatable_notes = MODULE.generate_finalizer_appendix(
            release=updatable,
            repo="POf-L/Fanqie-novel-Downloader",
            tag="unsigned-v2099.1.2-r2",
            version="2099.1.2",
            source_ref="main",
            source_commit="0123456789ab",
            platforms=platforms,
            mode="formal",
            highlights=[],
        )
        self.assertIn("可以在应用内更新", updatable_notes)
        self.assertIn("`unsigned/latest.json`", updatable_notes)
        MODULE.verify_device_guide(
            updatable_notes,
            platforms=platforms,
            updater_available=True,
            mode="formal",
        )

    def test_unsigned_finalizer_appends_device_guide_without_overwriting_draft(self):
        release = self.fixture()
        release["prerelease"] = False
        appendix = MODULE.generate_finalizer_appendix(
            release=release,
            repo="POf-L/Fanqie-novel-Downloader",
            tag="unsigned-v2099.1.1-r1",
            version="2099.1.1",
            source_ref="main",
            source_commit="0123456789ab",
            platforms=(
                "windows-x64, windows-arm64, linux-x64, linux-arm64, "
                "macos-x64, macos-arm64, android, ios"
            ),
            mode="formal",
            highlights=[],
        )
        original = "## 原 Draft 正文\n\n这是用户在构建期间看到的正文。"
        notes = MODULE.append_finalizer(original, appendix)
        self.assertTrue(notes.startswith(original))
        self.assertIn(MODULE.FINALIZER_START, notes)
        self.assertIn("## 下载地址", notes)
        self.assertIn("未知发布者", notes)
        self.assertIn("Gatekeeper", notes)
        self.assertIn("### ❓ 常见问题", notes)
        self.assertIn("### 💎 支持与推广", notes)
        self.assertIn("<summary>📦 构建信息</summary>", notes)
        for label in (
            "Windows",
            "macOS",
            "Linux",
            "Android",
            "iOS",
            "64位 arm64-v8a",
            "32位 armeabi-v7a",
            "x86_64",
            "通用版 universal",
            "Apple M 芯片",
            "Intel 芯片",
            "便携版（无需安装）",
            "APP 压缩包",
        ):
            self.assertIn(label, notes)
        windows_installer = notes.split("#### 安装包（推荐）", 1)[1].split(
            "#### 便携版（无需安装）", 1
        )[0]
        self.assertNotIn("portable.exe", windows_installer)
        macos_guide = notes.split("### 🍎 macOS", 1)[1].split(
            "### 🐧 Linux", 1
        )[0]
        self.assertIn("darwin-aarch64.zip", macos_guide)
        self.assertIn("darwin-x64.zip", macos_guide)
        rerun = MODULE.append_finalizer(notes, appendix.replace("下载时以本区块为准", "重跑已刷新"))
        self.assertEqual(rerun.count(MODULE.FINALIZER_START), 1)
        self.assertIn("重跑已刷新", rerun)
        MODULE.verify_device_guide(
            rerun,
            platforms=(
                "windows-x64, windows-arm64, linux-x64, linux-arm64, "
                "macos-x64, macos-arm64, android, ios"
            ),
            updater_available=False,
            mode="formal",
        )

    def test_partial_platform_guide_requires_only_selected_device_variants(self):
        release = self.fixture()
        release["assets"] = [
            asset
            for asset in release["assets"]
            if "windows-x64" in str(asset["name"])
        ]
        release["prerelease"] = False
        notes = MODULE.generate_finalizer_appendix(
            release=release,
            repo="POf-L/Fanqie-novel-Downloader",
            tag="unsigned-v2099.1.3-r3",
            version="2099.1.3",
            source_ref="main",
            source_commit="0123456789ab",
            platforms="windows-x64",
            mode="formal",
            highlights=[],
        )
        for heading in ("Windows", "macOS", "Linux", "Android", "iOS"):
            self.assertIn(heading, notes)
        self.assertIn("64位（常用）", notes)
        self.assertIn("windows-x64-portable.exe", notes)
        self.assertNotIn("Apple M 芯片", notes)
        self.assertNotIn("64位 arm64-v8a", notes)
        MODULE.verify_device_guide(
            notes,
            platforms="windows-x64",
            updater_available=False,
            mode="formal",
        )

    def test_append_removes_managed_draft_and_preserves_text_outside_markers(self):
        preface = "## 人工发布说明\n\n保留尾随空格。  \n\n"
        suffix = "\n\n人工补充。\n"
        original = (
            preface
            + MODULE.DRAFT_START
            + "\n> ⏳ **本版本正在构建中**。\n"
            + MODULE.DRAFT_END
            + suffix
        )
        appendix = (
            MODULE.FINALIZER_START
            + "\n设备指引\n"
            + MODULE.FINALIZER_END
        )
        notes = MODULE.append_finalizer(original, appendix)
        self.assertTrue(notes.startswith(preface + suffix))
        self.assertNotIn(MODULE.DRAFT_START, notes)
        self.assertNotIn(MODULE.LEGACY_DRAFT_STATUS, notes)
        refreshed = MODULE.append_finalizer(
            notes, appendix.replace("设备指引", "刷新后的设备指引")
        )
        self.assertTrue(refreshed.startswith(preface + suffix))
        self.assertEqual(refreshed.count(MODULE.FINALIZER_START), 1)
        self.assertIn("刷新后的设备指引", refreshed)

    def test_legacy_r643_draft_cleanup_is_explicit_and_strict(self):
        original = "\n".join(
            [
                "## 2026.8.7-445（未签名版）",
                "",
                "人工保留前言。",
                "",
                MODULE.LEGACY_DRAFT_STATUS,
                "> 下方下载链接**暂时指向最新已发布版本**。",
                "",
                "## 下载地址（默认：最新已发布版本）",
                "",
                "旧链接",
                "",
                "### 💎 支持与推广",
                "",
                "旧推广",
                "",
                "<details>",
                "- 正在构建版本：`2026.8.7-445`",
                "- 计划平台：windows-x64, linux-arm64",
                "</details>",
                "",
                MODULE.FINALIZER_START,
                "旧 finalizer",
                MODULE.FINALIZER_END,
            ]
        )
        appendix = (
            MODULE.FINALIZER_START
            + "\n新设备指引\n"
            + MODULE.FINALIZER_END
        )
        with self.assertRaisesRegex(SystemExit, "explicit maintenance"):
            MODULE.append_finalizer(original, appendix)
        cleaned = MODULE.append_finalizer(
            original, appendix, allow_legacy_draft=True
        )
        self.assertIn("人工保留前言", cleaned)
        self.assertIn("新设备指引", cleaned)
        self.assertNotIn("旧链接", cleaned)
        self.assertNotIn(MODULE.LEGACY_DRAFT_STATUS, cleaned)
        self.assertEqual(cleaned.count(MODULE.FINALIZER_START), 1)

    def test_arm64_appimage_aliases_render_one_signed_canonical_link(self):
        release = self.fixture()
        release["prerelease"] = False
        release["assets"].extend(
            [
                {
                    "name": "FanqieNovelDownloader-tauri-linux-arm64.AppImage",
                    "digest": "sha256:" + "0" * 64,
                },
                {"name": "latest.json", "digest": "sha256:" + "1" * 64},
                {
                    "name": "FanqieNovelDownloader-tauri-linux-aarch64.AppImage.sig",
                    "digest": "sha256:" + "2" * 64,
                },
            ]
        )
        notes = MODULE.generate_finalizer_appendix(
            release=release,
            repo="POf-L/Fanqie-novel-Downloader",
            tag="unsigned-v2099.1.4-r4",
            version="2099.1.4",
            source_ref="main",
            source_commit="0123456789ab",
            platforms=(
                "windows-x64, windows-arm64, linux-x64, linux-arm64, "
                "macos-x64, macos-arm64, android, ios"
            ),
            mode="formal",
            highlights=["- 修复登录窗口"],
        )
        self.assertEqual(notes.count("linux-aarch64.AppImage)"), 1)
        self.assertNotIn("linux-arm64.AppImage)", notes)
        self.assertIn("## 本次修复", notes)
        self.assertIn("修复登录窗口", notes)

    def test_draft_merge_refreshes_only_the_managed_block(self):
        existing = (
            "人工前言\n\n"
            + MODULE.DRAFT_START
            + "\n旧状态\n"
            + MODULE.DRAFT_END
            + "\n\n人工结尾\n"
        )
        generated = (
            "机器前言不应覆盖\n\n"
            + MODULE.DRAFT_START
            + "\n新状态\n"
            + MODULE.DRAFT_END
            + "\n"
        )
        merged = MODULE.merge_unsigned_draft(existing, generated)
        self.assertTrue(merged.startswith("人工前言"))
        self.assertIn("人工结尾", merged)
        self.assertIn("新状态", merged)
        self.assertNotIn("旧状态", merged)
        self.assertNotIn("机器前言不应覆盖", merged)
        self.assertEqual(merged.count(MODULE.DRAFT_START), 1)

    def test_draft_merge_rejects_unmarked_legacy_body(self):
        existing = "\n".join(
            [
                "人工前言",
                "",
                MODULE.LEGACY_DRAFT_STATUS,
                "> 下方下载链接**暂时指向最新已发布版本**。",
                "## 下载地址（默认：最新已发布版本）",
                "### 💎 支持与推广",
                "<details>",
                "- 正在构建版本：`old`",
                "- 计划平台：windows-x64",
                "</details>",
            ]
        )
        generated = (
            MODULE.DRAFT_START
            + "\n新状态\n"
            + MODULE.DRAFT_END
            + "\n"
        )
        with self.assertRaisesRegex(SystemExit, "explicit maintenance"):
            MODULE.merge_unsigned_draft(existing, generated)

    def test_unsigned_prerelease_guide_does_not_claim_fixed_alias_ownership(self):
        release = self.fixture()
        release["prerelease"] = True
        release["assets"].extend(
            [
                {"name": "latest.json", "digest": "sha256:" + "1" * 64},
                {
                    "name": "FanqieNovelDownloader-tauri-windows-x64-setup.exe.sig",
                    "digest": "sha256:" + "2" * 64,
                },
            ]
        )
        notes = MODULE.generate_finalizer_appendix(
            release=release,
            repo="POf-L/Fanqie-novel-Downloader",
            tag="unsigned-v2099.1.2-r2",
            version="2099.1.2",
            source_ref="main",
            source_commit="0123456789ab",
            platforms=(
                "windows-x64, windows-arm64, linux-x64, linux-arm64, "
                "macos-x64, macos-arm64, android, ios"
            ),
            mode="prerelease",
            highlights=[],
        )
        self.assertIn("不进入固定 `unsigned` 别名", notes)
        self.assertNotIn("客户端通过固定 `unsigned/latest.json`", notes)

    def test_formal_publication_sets_make_latest_true(self):
        captured = {}

        def fake_gh_json(arguments, *, input_text=None):
            captured["arguments"] = arguments
            captured["payload"] = json.loads(input_text)
            return {"draft": False, "prerelease": False}

        with patch.object(MODULE, "gh_json", side_effect=fake_gh_json):
            MODULE.publish_release(
                repo="POf-L/Fanqie-novel-Downloader",
                database_id=123,
                tag="unsigned-v2099.1.1-r1",
                title="Unsigned",
                notes="Notes",
                mode="formal",
            )

        self.assertEqual(captured["payload"]["make_latest"], "true")
        self.assertEqual(captured["payload"]["prerelease"], False)
        self.assertEqual(captured["payload"]["draft"], False)
        self.assertEqual(captured["arguments"][-2:], ["--input", "-"])

    def test_formal_latest_verification_allows_bounded_github_propagation(self):
        with (
            patch.object(
                MODULE,
                "latest_tag",
                side_effect=["v2098.1.1", "unsigned-v2099.1.1-r1"],
            ) as latest_tag,
            patch.object(MODULE.time, "sleep") as sleep,
        ):
            observed = MODULE.wait_for_latest_tag(
                "POf-L/Fanqie-novel-Downloader",
                "unsigned-v2099.1.1-r1",
                attempts=2,
                delay_seconds=0.01,
            )
        self.assertEqual(observed, "unsigned-v2099.1.1-r1")
        self.assertEqual(latest_tag.call_count, 2)
        sleep.assert_called_once_with(0.01)

    def test_manifest_asset_digest_must_match_uploaded_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.MANIFEST_NAME
            path.write_text("0" * 64 + "  app.exe\n", encoding="utf-8")
            digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            release = {"assets": [{"name": MODULE.MANIFEST_NAME, "digest": digest}]}
            MODULE.verify_manifest_asset(release, path)
            release["assets"][0]["digest"] = "sha256:" + "f" * 64
            with self.assertRaisesRegex(SystemExit, "digest does not match"):
                MODULE.verify_manifest_asset(release, path)

    def test_existing_manifest_can_resume_channel_without_republishing(self):
        release = self.fixture()
        assets = MODULE.payload_assets(release)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.MANIFEST_NAME
            MODULE.write_manifest(assets, path)
            digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            release["assets"].append(
                {
                    "name": MODULE.MANIFEST_NAME,
                    "digest": digest,
                }
            )
        self.assertTrue(MODULE.existing_manifest_is_current(release, assets))

        release["assets"][0]["digest"] = "sha256:" + "f" * 64
        changed_assets = MODULE.payload_assets(release)
        self.assertFalse(
            MODULE.existing_manifest_is_current(release, changed_assets)
        )

    def test_finalizer_markers_identify_an_already_finalized_release(self):
        body = (
            "原始 Draft 正文\n\n"
            + MODULE.FINALIZER_START
            + "\n设备指引\n"
            + MODULE.FINALIZER_END
        )
        self.assertIn(MODULE.FINALIZER_START, body)
        self.assertEqual(body.count(MODULE.FINALIZER_START), 1)


if __name__ == "__main__":
    unittest.main()
