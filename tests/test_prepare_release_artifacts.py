import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare-release-artifacts.py"
REPO = "POf-L/Fanqie-novel-Downloader"
TAG = "v2026.7.23-524"


class PrepareReleaseArtifactsTest(unittest.TestCase):
    def fixture(self):
        return {
            "tag_name": TAG,
            "draft": True,
            "prerelease": False,
            "body": "\n".join(
                [
                    "- 源码引用：`main`",
                    "- 源码提交：`cb131f422564`",
                    "- 计划平台：windows-x64, android",
                ]
            ),
            "assets": [
                {
                    "name": "Fanqie Downloader windows-x64-setup.exe",
                    "digest": "sha256:" + "a" * 64,
                },
                {
                    "name": "latest.json",
                    "digest": "sha256:" + "b" * 64,
                },
                {
                    "name": "ABIS.txt",
                    "digest": "sha256:" + "c" * 64,
                },
                {
                    "name": "SHA256SUMS-release.txt",
                    "digest": "sha256:" + "d" * 64,
                },
            ],
        }

    def run_preparer(self, release, *, check=False, mutate_manifest=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        release_path = directory / "release.json"
        notes_path = directory / "release-notes.md"
        manifest_path = directory / "SHA256SUMS-release.txt"
        release_path.write_text(json.dumps(release), encoding="utf-8")
        command = [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release_path),
            "--repo",
            REPO,
            "--tag",
            TAG,
            "--manifest",
            str(manifest_path),
        ]
        if check:
            manifest_path.write_text(mutate_manifest or "", encoding="utf-8")
            command.append("--check")
        else:
            command.extend(["--notes", str(notes_path)])
        result = subprocess.run(command, capture_output=True, text=True)
        return result, notes_path, manifest_path

    def test_generates_notes_and_manifest_from_authenticated_digests(self):
        result, notes_path, manifest_path = self.run_preparer(self.fixture())

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = manifest_path.read_text(encoding="utf-8")
        self.assertEqual(len(manifest.splitlines()), 3)
        self.assertIn("a" * 64 + "  Fanqie Downloader windows-x64-setup.exe", manifest)
        self.assertIn("b" * 64 + "  latest.json", manifest)
        self.assertNotIn("SHA256SUMS-release.txt", manifest)

        notes = notes_path.read_text(encoding="utf-8")
        self.assertIn("源码提交：`cb131f422564`", notes)
        self.assertIn("## 2026.7.23-524（正式版）", notes)
        self.assertIn(
            "releases/download/v2026.7.23-524/"
            "Fanqie%20Downloader%20windows-x64-setup.exe",
            notes,
        )

        self.assertIn("## 平台状态与安装限制", notes)
        self.assertIn("Windows", notes)
        self.assertIn("Authenticode", notes)
        self.assertIn("macOS", notes)
        self.assertIn("Developer ID", notes)
        self.assertIn("Linux", notes)
        self.assertIn("- **Linux**：本版本未提供安装包", notes)
        self.assertIn("Android", notes)
        self.assertIn("缺少发布 keystore", notes)
        self.assertIn("iOS", notes)
        self.assertIn("- **iOS**：本版本未提供 IPA", notes)
        self.assertIn("自动更新", notes)

    def test_platform_status_reports_signed_android_and_unsigned_macos(self):
        release = self.fixture()
        release["prerelease"] = True
        release["assets"].extend(
            [
                {
                    "name": "FanqieNovelDownloader-tauri-darwin-aarch64-unsigned.dmg",
                    "digest": "sha256:" + "e" * 64,
                },
                {
                    "name": "FanqieNovelDownloader-2026.7.23-524-android-arm64-v8a.apk",
                    "digest": "sha256:" + "f" * 64,
                },
                {
                    "name": "SIGNING.txt",
                    "digest": "sha256:" + "1" * 64,
                },
                {
                    "name": "FanqieNovelDownloader-2026.7.23-524-Fanqie.Novel.Downloader.ipa",
                    "digest": "sha256:" + "2" * 64,
                },
            ]
        )

        result, notes_path, _ = self.run_preparer(release)

        self.assertEqual(result.returncode, 0, result.stderr)
        notes = notes_path.read_text(encoding="utf-8")
        self.assertIn("未签名、未公证的预发布包", notes)
        self.assertIn("使用发布密钥签名并经 `apksigner` 验证", notes)
        self.assertIn("无 Apple 签名侧载模式", notes)
        self.assertIn("这是 prerelease", notes)

    def test_check_rejects_a_stale_digest(self):
        release = self.fixture()
        stale = "0" * 64 + "  latest.json\n"

        result, _, _ = self.run_preparer(
            release, check=True, mutate_manifest=stale
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match GitHub asset digests", result.stderr)

    def test_missing_github_digest_is_a_hard_failure(self):
        release = self.fixture()
        release["assets"][0]["digest"] = None

        result, _, _ = self.run_preparer(release)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no valid GitHub SHA-256 digest", result.stderr)


if __name__ == "__main__":
    unittest.main()
