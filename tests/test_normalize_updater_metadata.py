import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "normalize-updater-metadata.py"


class NormalizeUpdaterMetadataTest(unittest.TestCase):
    def run_normalizer(self, metadata, assets, *extra):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            metadata_path = directory / "latest.json"
            assets_path = directory / "release.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            assets_path.write_text(json.dumps(assets), encoding="utf-8")
            command = [
                sys.executable,
                str(SCRIPT),
                "--metadata",
                str(metadata_path),
                "--assets",
                str(assets_path),
                "--repo",
                "POf-L/Fanqie-novel-Downloader",
                "--tag",
                "v2026.7.23-1200",
                *extra,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            return result, json.loads(metadata_path.read_text(encoding="utf-8"))

    def test_api_asset_urls_are_rewritten_to_browser_download_urls(self):
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {
                "windows-x86_64": {
                    "signature": "sig-win",
                    "url": "https://api.github.com/repos/POf-L/Fanqie-novel-Downloader/releases/assets/101",
                },
                "linux-x86_64": {
                    "signature": "sig-linux",
                    "url": "https://api.github.com/repos/POf-L/Fanqie-novel-Downloader/releases/assets/102",
                },
            },
        }
        assets = {
            "assets": [
                {
                    "id": 101,
                    "name": "Fanqie-windows.exe",
                    "browser_download_url": "https://github.com/POf-L/Fanqie-novel-Downloader/releases/download/v2026.7.23-1200/Fanqie-windows.exe",
                },
                {
                    "id": 102,
                    "name": "Fanqie-linux.AppImage",
                    "browser_download_url": "https://github.com/POf-L/Fanqie-novel-Downloader/releases/download/v2026.7.23-1200/Fanqie-linux.AppImage",
                },
            ]
        }
        result, normalized = self.run_normalizer(metadata, assets)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            normalized["platforms"]["windows-x86_64"]["url"],
            assets["assets"][0]["browser_download_url"],
        )
        self.assertEqual(
            normalized["platforms"]["linux-x86_64"]["url"],
            assets["assets"][1]["browser_download_url"],
        )

        check, checked = self.run_normalizer(normalized, assets, "--check")
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(checked, normalized)

    def test_missing_asset_is_a_hard_failure(self):
        metadata = {
            "platforms": {
                "windows-x86_64": {
                    "signature": "sig",
                    "url": "https://api.github.com/repos/POf-L/Fanqie-novel-Downloader/releases/assets/999",
                }
            }
        }
        result, _ = self.run_normalizer(metadata, {"assets": []})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("named assets", result.stderr)

    def test_signature_asset_cannot_be_selected_as_the_update_payload(self):
        metadata = {
            "platforms": {
                "windows-x86_64": {
                    "signature": "sig",
                    "url": "https://api.github.com/repos/POf-L/Fanqie-novel-Downloader/releases/assets/1000",
                }
            }
        }
        assets = {
            "assets": [
                {
                    "id": 1000,
                    "name": "Fanqie-windows.exe.sig",
                    "browser_download_url": "https://github.com/POf-L/Fanqie-novel-Downloader/releases/download/v2026.7.23-1200/Fanqie-windows.exe.sig",
                }
            ]
        }
        result, _ = self.run_normalizer(metadata, assets)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("metadata/signature", result.stderr)


if __name__ == "__main__":
    unittest.main()
