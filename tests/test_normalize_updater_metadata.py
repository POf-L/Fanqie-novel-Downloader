import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "normalize-updater-metadata.py"
REPO = "POf-L/Fanqie-novel-Downloader"
TAG = "v2026.7.23-1200"


def updater_signature(filename: str, nonce: str = "1") -> str:
    payload = (
        "untrusted comment: signature from tauri secret key\n"
        f"placeholder-{nonce}\n"
        f"trusted comment: timestamp:{nonce}\tfile:{filename}\n"
        f"signature-{nonce}\n"
    )
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def raw_updater_signature(filename: str, nonce: str = "1") -> str:
    return (
        "untrusted comment: signature from tauri secret key\n"
        f"placeholder-{nonce}\n"
        f"trusted comment: timestamp:{nonce}\tfile:{filename}\n"
        f"signature-{nonce}\n"
    )


def asset(name: str, asset_id: int) -> dict:
    return {
        "id": asset_id,
        "name": name,
        "browser_download_url": (
            f"https://github.com/{REPO}/releases/download/{TAG}/{name}"
        ),
    }


class NormalizeUpdaterMetadataTest(unittest.TestCase):
    def run_normalizer(self, metadata, assets, signatures, *extra, tag=TAG):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            metadata_path = directory / "latest.json"
            assets_path = directory / "release.json"
            signatures_path = directory / "signatures"
            signatures_path.mkdir()
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            assets_path.write_text(json.dumps({"assets": assets}), encoding="utf-8")
            for name, value in signatures.items():
                (signatures_path / name).write_bytes(value.encode("utf-8"))
            command = [
                sys.executable,
                str(SCRIPT),
                "--metadata",
                str(metadata_path),
                "--assets",
                str(assets_path),
                "--signatures-dir",
                str(signatures_path),
                "--repo",
                REPO,
                "--tag",
                tag,
                *extra,
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            return result, json.loads(metadata_path.read_text(encoding="utf-8"))

    def windows_x64_release(self):
        setup = "FanqieNovelDownloader-tauri-windows-x64-setup.exe"
        portable = "FanqieNovelDownloader-tauri-windows-x64-portable.exe"
        assets = [
            asset(setup, 101),
            asset(f"{setup}.sig", 102),
            asset(portable, 103),
            asset(f"{portable}.sig", 104),
            asset("latest.json", 105),
        ]
        signatures = {
            f"{setup}.sig": updater_signature(
                "Fanqie Novel Downloader_2026.7.23-1200_x64-setup.exe", "101"
            ),
            f"{portable}.sig": updater_signature(portable, "102"),
        }
        return setup, portable, assets, signatures

    def test_rebuilds_only_exact_package_specific_entries(self):
        setup, portable, assets, signatures = self.windows_x64_release()
        deb = "FanqieNovelDownloader-tauri-linux-amd64.deb"
        appimage = "FanqieNovelDownloader-tauri-linux-amd64.AppImage"
        app = "FanqieNovelDownloader-tauri-darwin-aarch64.app.tar.gz"
        for index, (name, signed_name) in enumerate(
            (
                (deb, "Fanqie Novel Downloader_2026.7.23-1200_amd64.deb"),
                (
                    appimage,
                    "Fanqie Novel Downloader_2026.7.23-1200_amd64.AppImage",
                ),
                (app, "Fanqie Novel Downloader.app.tar.gz"),
            ),
            start=200,
        ):
            assets.extend([asset(name, index), asset(f"{name}.sig", index + 20)])
            signatures[f"{name}.sig"] = updater_signature(signed_name, str(index))

        metadata = {
            "version": "2026.7.23-1200",
            "notes": "test",
            "platforms": {
                "windows-x86_64": {"signature": "old", "url": "setup.exe"},
                "linux-x86_64": {"signature": "old", "url": "first-asset"},
                "darwin-aarch64": {"signature": "old", "url": "app"},
            },
        }
        result, normalized = self.run_normalizer(metadata, assets, signatures)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            set(normalized["platforms"]),
            {
                "windows-x86_64-nsis",
                "windows-x86_64-portable",
                "linux-x86_64-deb",
                "linux-x86_64-appimage",
                "darwin-aarch64-app",
            },
        )
        self.assertTrue(
            normalized["platforms"]["windows-x86_64-nsis"]["url"].endswith(
                f"/{setup}"
            )
        )
        self.assertTrue(
            normalized["platforms"]["windows-x86_64-portable"]["url"].endswith(
                f"/{portable}"
            )
        )
        self.assertNotIn("windows-x86_64", normalized["platforms"])
        self.assertNotIn("linux-x86_64", normalized["platforms"])
        self.assertNotIn("darwin-aarch64", normalized["platforms"])

        check, checked = self.run_normalizer(
            normalized, assets, signatures, "--check"
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(checked, normalized)

    def test_check_rejects_generic_desktop_keys(self):
        _, _, assets, signatures = self.windows_x64_release()
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {
                "windows-x86_64": {
                    "signature": "stale",
                    "url": "https://example.invalid/setup.exe",
                }
            },
        }
        result, _ = self.run_normalizer(
            metadata, assets, signatures, "--check"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("generic_or_unknown", result.stderr)

    def test_decoded_minisign_file_is_reencoded_for_tauri_metadata(self):
        _, portable, assets, signatures = self.windows_x64_release()
        raw = raw_updater_signature(portable, "decoded")
        signatures[f"{portable}.sig"] = raw
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }

        result, normalized = self.run_normalizer(metadata, assets, signatures)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            normalized["platforms"]["windows-x86_64-portable"]["signature"],
            base64.b64encode(raw.encode("utf-8")).decode("ascii"),
        )

    def test_check_rejects_portable_entry_pointing_to_setup(self):
        setup, _, assets, signatures = self.windows_x64_release()
        seed = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, normalized = self.run_normalizer(seed, assets, signatures)
        self.assertEqual(result.returncode, 0, result.stderr)
        normalized["platforms"]["windows-x86_64-portable"]["url"] = (
            f"https://github.com/{REPO}/releases/download/{TAG}/{setup}"
        )
        check, _ = self.run_normalizer(
            normalized, assets, signatures, "--check"
        )
        self.assertNotEqual(check.returncode, 0)
        self.assertIn("mismatched", check.stderr)

    def test_windows_release_requires_setup_portable_and_both_signatures(self):
        _, portable, assets, signatures = self.windows_x64_release()
        assets = [item for item in assets if item["name"] != f"{portable}.sig"]
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, _ = self.run_normalizer(metadata, assets, signatures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Windows x64 release shape is incomplete", result.stderr)

    def test_missing_downloaded_signature_is_a_hard_failure(self):
        _, portable, assets, signatures = self.windows_x64_release()
        signatures.pop(f"{portable}.sig")
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, _ = self.run_normalizer(metadata, assets, signatures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("downloaded signature file is missing", result.stderr)

    def test_portable_signature_must_be_for_the_final_portable_name(self):
        _, portable, assets, signatures = self.windows_x64_release()
        signatures[f"{portable}.sig"] = updater_signature(
            "Fanqie Novel Downloader_2026.7.23-1200_x64-setup.exe", "bad"
        )
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, _ = self.run_normalizer(metadata, assets, signatures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("final asset name", result.stderr)

    def test_cross_architecture_signature_is_rejected(self):
        setup, _, assets, signatures = self.windows_x64_release()
        signatures[f"{setup}.sig"] = updater_signature(
            "Fanqie Novel Downloader_2026.7.23-1200_arm64-setup.exe", "bad-arch"
        )
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, _ = self.run_normalizer(metadata, assets, signatures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("signature architecture", result.stderr)

    def test_signatures_cannot_be_reused_across_packages(self):
        setup, portable, assets, signatures = self.windows_x64_release()
        shared = updater_signature(portable, "shared")
        signatures[f"{setup}.sig"] = shared
        signatures[f"{portable}.sig"] = shared
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, _ = self.run_normalizer(metadata, assets, signatures)
        self.assertNotEqual(result.returncode, 0)
        # The setup entry fails type validation first, which is equally strict.
        self.assertRegex(result.stderr, "payload type|same updater signature")

    def test_unknown_desktop_signature_asset_is_rejected(self):
        _, _, assets, signatures = self.windows_x64_release()
        unknown = "FanqieNovelDownloader-tauri-windows-x64-debug.zip.sig"
        assets.append(asset(unknown, 900))
        signatures[unknown] = updater_signature("debug.zip", "900")
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, _ = self.run_normalizer(metadata, assets, signatures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported updater signature", result.stderr)

    def test_stale_metadata_version_is_a_hard_failure(self):
        _, _, assets, signatures = self.windows_x64_release()
        metadata = {
            "version": "2026.7.21-1511",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, _ = self.run_normalizer(metadata, assets, signatures)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("version does not match", result.stderr)

    def test_unsigned_release_tag_uses_embedded_application_version(self):
        _, _, assets, signatures = self.windows_x64_release()
        metadata = {
            "version": "2026.7.23-1200",
            "platforms": {"windows-x86_64": {"signature": "old", "url": "old"}},
        }
        result, normalized = self.run_normalizer(
            metadata,
            assets,
            signatures,
            tag="unsigned-v2026.7.23-1200-r88",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in normalized["platforms"].values():
            self.assertIn("/download/unsigned-v2026.7.23-1200-r88/", entry["url"])


if __name__ == "__main__":
    unittest.main()
