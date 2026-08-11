import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit-release-assets.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fanqie_asset_audit", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load release asset auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load_module()


class ReleaseAssetAuditTest(unittest.TestCase):
    def test_current_package_and_signature_names_are_allowlisted(self):
        names = (
            "FanqieNovelDownloader-tauri-windows-x64-setup.exe",
            "FanqieNovelDownloader-tauri-windows-x64-setup.exe.sig",
            "FanqieNovelDownloader-tauri-windows-x64-portable.exe",
            "FanqieNovelDownloader-tauri-windows-x64-portable.exe.sig",
            "FanqieNovelDownloader-tauri-linux-amd64.deb",
            "FanqieNovelDownloader-tauri-linux-amd64.deb.sig",
            "FanqieNovelDownloader-tauri-linux-amd64.AppImage",
            "FanqieNovelDownloader-tauri-linux-amd64.AppImage.sig",
            "FanqieNovelDownloader-tauri-darwin-aarch64.app.tar.gz",
            "FanqieNovelDownloader-tauri-darwin-aarch64.app.tar.gz.sig",
            "FanqieNovelDownloader-tauri-darwin-aarch64.dmg",
            "FanqieNovelDownloader-tauri-darwin-aarch64.zip",
            "FanqieNovelDownloader-2026.8.11-android-arm64-v8a.apk",
            "FanqieNovelDownloader-2026.8.11-android.aab",
            "FanqieNovelDownloader-2026.8.11-Fanqie.Novel.Downloader.ipa",
            "latest.json",
            "SHA256SUMS-release.txt",
            "SIGNING.txt",
        )
        for name in names:
            with self.subTest(name=name):
                AUDIT.validate_asset_name(name)

    def test_source_debug_and_unknown_assets_are_rejected(self):
        for name in (
            "Cargo.toml",
            "FanqieNovelDownloader-private-src.zip",
            "FanqieNovelDownloader-tauri-windows-x64.pdb",
            "FanqieNovelDownloader-tauri-windows-x64-debug.zip",
            "random-output.bin",
        ):
            with self.subTest(name=name), self.assertRaises(SystemExit):
                AUDIT.validate_asset_name(name)

    def test_frontend_javascript_inside_a_packaged_app_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "FanqieNovelDownloader-tauri-darwin-x64.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(
                    "Fanqie Novel Downloader.app/Contents/Resources/web/static/app.js",
                    "console.log('packaged frontend');",
                )
                output.writestr(
                    "Fanqie Novel Downloader.app/Contents/MacOS/fanqie-desktop",
                    b"binary",
                )
            AUDIT.scan_zip(archive)

    def test_archive_source_maps_rust_source_and_private_checkout_are_rejected(self):
        members = (
            "Fanqie.app/Contents/Resources/app.js.map",
            "Fanqie.app/Contents/Resources/state.rs",
            "private-src/src-tauri/tauri.conf.json",
            ".git/config",
        )
        for index, member in enumerate(members):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as directory:
                archive = Path(directory) / f"FanqieNovelDownloader-test-{index}.zip"
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr(member, "not public")
                with self.assertRaises(SystemExit):
                    AUDIT.scan_zip(archive)

    def test_downloaded_asset_set_must_match_release_json(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            release_path = directory / "release.json"
            release_path.write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "name": "FanqieNovelDownloader-tauri-windows-x64-portable.exe"
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            root = directory / "assets"
            root.mkdir()
            (root / "SIGNING.txt").write_text("unexpected", encoding="utf-8")
            names = set(AUDIT.release_asset_names(release_path))
            with self.assertRaises(SystemExit):
                AUDIT.audit_downloaded_assets(root, names)

    def test_raw_private_path_and_token_values_are_rejected(self):
        samples = (
            b"compiled path private-src\\src-tauri\\src\\backend\\state.rs",
            b"github token " + b"gho_" + (b"a" * 36),
        )
        for index, payload in enumerate(samples):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / (
                    f"FanqieNovelDownloader-tauri-windows-x64-portable-{index}.exe"
                )
                path.write_bytes(payload)
                with self.assertRaises(SystemExit):
                    AUDIT.scan_raw_markers(path)


if __name__ == "__main__":
    unittest.main()
