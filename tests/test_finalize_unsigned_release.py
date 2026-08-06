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
            "FanqieNovelDownloader-tauri-linux-arm64.AppImage",
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

    def test_formal_notes_explain_manual_installation(self):
        notes = MODULE.generate_notes(
            repo="POf-L/Fanqie-novel-Downloader",
            tag="unsigned-v2099.1.1-r1",
            version="2099.1.1",
            source_ref="main",
            source_commit="0123456789ab",
            platforms="windows-x64, macos-arm64, ios",
            stable_tag="v2098.1.1",
            installers=["app.exe", "app.dmg", "app.ipa"],
            mode="formal",
            highlights=[],
        )
        self.assertIn("未签名版本，不支持自动更新", notes)
        self.assertIn("GitHub Latest", notes)
        self.assertIn("stable/latest.json", notes)
        self.assertIn("未知发布者", notes)
        self.assertIn("Gatekeeper", notes)
        self.assertIn("AltStore", notes)
        self.assertIn("`latest.json`", notes)
        self.assertIn("0123456789ab", notes)

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


if __name__ == "__main__":
    unittest.main()
