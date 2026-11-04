import importlib.util
import plistlib
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")
SETUP = (ROOT / "scripts" / "setup-macos-cross.sh").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location("bundle_macos_cross", ROOT / "scripts" / "bundle-macos-cross.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def fake_macho(cputype, libs, minos=(11, 0), filetype=2):
    commands = b""
    for lib in libs:
        name = lib.encode() + b"\0"
        size = (24 + len(name) + 7) // 8 * 8
        commands += struct.pack("<IIIIII", 0x0C, size, 24, 2, 0, 0) + name.ljust(size - 24, b"\0")
    raw_minos = (minos[0] << 16) | (minos[1] << 8)
    commands += struct.pack("<IIIIII", 0x32, 24, 1, raw_minos, raw_minos, 0)
    ncmds = len(libs) + 1
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, cputype, 0, filetype, ncmds, len(commands), 0, 0)
    return header + commands


SYSTEM_LIBS = [
    "/System/Library/Frameworks/WebKit.framework/Versions/A/WebKit",
    "/System/Library/Frameworks/AppKit.framework/Versions/C/AppKit",
    "/System/Library/Frameworks/Foundation.framework/Versions/C/Foundation",
    "/usr/lib/libSystem.B.dylib",
]


class MacosCrossWorkflowTest(unittest.TestCase):
    def test_both_macos_targets_fall_back_to_linux_cross_build(self):
        self.assertEqual(WORKFLOW.count('"fallback_os": "ubuntu-24.04",\n                  "fallback_bundles": "app,dmg"'), 2)
        self.assertNotIn('"fallback_os": "macos-latest"', WORKFLOW)
        self.assertIn("timeout-minutes: ${{ startsWith(matrix.platform, 'macos-') && 45 || 90 }}", WORKFLOW)

    def test_cross_path_replaces_tauri_action_only_for_darwin_on_linux(self):
        self.assertIn("bash release-wrapper/scripts/setup-macos-cross.sh", WORKFLOW)
        self.assertIn("--no-bundle --runner cargo-zigbuild", WORKFLOW)
        self.assertIn("bundle-macos-cross.py", WORKFLOW)
        self.assertIn(
            "if: steps.need.outputs.run == 'true' && !(runner.os == 'Linux' && endsWith(matrix.target, '-apple-darwin'))",
            WORKFLOW,
        )
        self.assertIn('tauri signer sign "${archive}"', WORKFLOW)
        self.assertIn("FanqieNovelDownloader-tauri-darwin-${arch}.app.tar.gz", WORKFLOW)

    def test_finalizers_accept_native_failure_covered_by_fallback(self):
        # GitHub cancels macOS jobs that wait 15 minutes for a runner; the
        # matrix then reports failure even though the fallback filled the gap.
        accepted = (
            "(needs.desktop.result == 'success' || needs.desktop.result == 'skipped' || "
            "(needs.desktop.result == 'failure' && needs.desktop-fallback.result == 'success')) &&"
        )
        self.assertEqual(WORKFLOW.count(accepted), 2)
        self.assertNotIn(
            "(needs.desktop.result == 'success' || needs.desktop.result == 'skipped') &&",
            WORKFLOW,
        )

    def test_signed_macos_release_never_uses_cross_build(self):
        self.assertIn("Refuse signed macOS builds on Linux", WORKFLOW)

    def test_zip_without_ditto_keeps_unix_modes(self):
        self.assertEqual(WORKFLOW.count('if shutil.which("ditto"):'), 2)
        self.assertIn("info.external_attr = (path.lstat().st_mode & 0xFFFF) << 16", WORKFLOW)

    def test_setup_downloads_are_pinned_and_checked(self):
        self.assertIn("sha256sum --check", SETUP)
        for name in ("ZIG_SHA256", "CARGO_ZIGBUILD_SHA256", "RCODESIGN_SHA256", "MACOS_SDK_SHA256"):
            self.assertRegex(SETUP, name + r'="[0-9a-f]{64}"')
        self.assertIn('ZIG_VERSION="0.13.0"', SETUP)
        self.assertRegex(SETUP, r'LIBDMG_COMMIT="[0-9a-f]{40}"')


class BundleMacosCrossTest(unittest.TestCase):
    def write(self, directory, data):
        path = Path(directory) / "fanqie-desktop"
        path.write_bytes(data)
        return path

    def test_accepts_arm64_binary_linking_only_system_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, fake_macho(0x0100000C, SYSTEM_LIBS))
            info = bundle.check_binary(path, "aarch64-apple-darwin", "10.13")
            self.assertEqual(info["minos"], (11, 0))

    def test_rejects_wrong_architecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, fake_macho(0x01000007, SYSTEM_LIBS))
            with self.assertRaises(bundle.BundleError):
                bundle.check_binary(path, "aarch64-apple-darwin", "10.13")

    def test_rejects_non_system_library_and_missing_webkit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, fake_macho(0x0100000C, SYSTEM_LIBS + ["/opt/homebrew/lib/libfoo.dylib"]))
            with self.assertRaises(bundle.BundleError):
                bundle.check_binary(path, "aarch64-apple-darwin", "10.13")
            path = self.write(tmp, fake_macho(0x0100000C, SYSTEM_LIBS[1:]))
            with self.assertRaises(bundle.BundleError):
                bundle.check_binary(path, "aarch64-apple-darwin", "10.13")

    def test_rejects_newer_minimum_macos_than_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, fake_macho(0x01000007, SYSTEM_LIBS, minos=(14, 0)))
            with self.assertRaises(bundle.BundleError):
                bundle.check_binary(path, "x86_64-apple-darwin", "10.13")

    def test_app_layout_matches_native_tauri_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tauri_dir = tmp / "src-tauri"
            (tauri_dir / "icons").mkdir(parents=True)
            (tauri_dir / "icons" / "icon.icns").write_bytes(b"icns")
            (tauri_dir / "licenses").mkdir()
            (tauri_dir / "licenses" / "L.html").write_text("x")
            config = {
                "productName": "Fanqie Novel Downloader",
                "identifier": "com.example.app",
                "bundle": {
                    "icon": ["icons/icon.png", "icons/icon.icns"],
                    "resources": {"licenses/L.html": "THIRD_PARTY_LICENSES.html"},
                    "copyright": "C",
                },
            }
            binary = self.write(tmp, fake_macho(0x0100000C, SYSTEM_LIBS))
            app = bundle.build_app(config, tauri_dir, binary, "2026.1.1-0000", tmp / "out")
            contents = app / "Contents"
            self.assertEqual(app.name, "Fanqie Novel Downloader.app")
            self.assertEqual((contents / "MacOS" / "fanqie-desktop").stat().st_mode & 0o777, 0o755)
            self.assertTrue((contents / "Resources" / "icon.icns").is_file())
            self.assertTrue((contents / "Resources" / "THIRD_PARTY_LICENSES.html").is_file())
            plist = plistlib.loads((contents / "Info.plist").read_bytes())
            self.assertEqual(plist["CFBundleExecutable"], "fanqie-desktop")
            self.assertEqual(plist["CFBundleIdentifier"], "com.example.app")
            self.assertEqual(plist["CFBundleShortVersionString"], "2026.1.1-0000")
            self.assertEqual(plist["LSMinimumSystemVersion"], "10.13")
            self.assertEqual(plist["NSHumanReadableCopyright"], "C")
            archive = bundle.make_updater_archive(app)
            import tarfile

            with tarfile.open(archive) as tar:
                names = tar.getnames()
                exe = tar.getmember("Fanqie Novel Downloader.app/Contents/MacOS/fanqie-desktop")
            self.assertEqual(names[0], "Fanqie Novel Downloader.app")
            self.assertEqual(exe.mode & 0o777, 0o755)


if __name__ == "__main__":
    unittest.main()
