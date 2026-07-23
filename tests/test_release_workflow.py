import io
import json
import os
import re
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-release.yml"
REPAIR_WORKFLOW = ROOT / ".github" / "workflows" / "repair-updater-metadata.yml"
FINALIZE_WORKFLOW = ROOT / ".github" / "workflows" / "finalize-draft-release.yml"
FINALIZER = ROOT / "scripts" / "finalize-release.py"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.repair_workflow = REPAIR_WORKFLOW.read_text(encoding="utf-8")
        cls.finalize_workflow = FINALIZE_WORKFLOW.read_text(encoding="utf-8")
        cls.finalizer = FINALIZER.read_text(encoding="utf-8")
        cls.ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def render_draft_notes(self, asset_names):
        script = self.workflow.split("          python - <<'PY'\n", 1)[1]
        script = textwrap.dedent(script.split("\n          PY", 1)[0])
        releases = [
            {
                "draft": False,
                "tag_name": "vprevious",
                "name": "Previous release",
                "assets": [{"name": name} for name in asset_names],
            }
        ]
        response = io.BytesIO(json.dumps(releases).encode("utf-8"))
        written = {}

        def capture_write_text(path, data, encoding=None):
            written[str(path)] = data
            return len(data)

        environment = {
            "GH_TOKEN": "test-token",
            "GH_REPO": "POf-L/Fanqie-novel-Downloader",
            "VERSION": "2099.1.1",
            "TAG_NAME": "v2099.1.1",
            "PRERELEASE": "false",
            "SOURCE_REF": "main",
            "SOURCE_COMMIT": "0123456789ab",
            "PLATFORMS": "android,ios",
        }
        with (
            patch.dict(os.environ, environment),
            patch("urllib.request.urlopen", return_value=response),
            patch.object(Path, "write_text", new=capture_write_text),
            patch("builtins.print"),
        ):
            exec(compile(script, str(WORKFLOW), "exec"), {})

        self.assertEqual(set(written), {"release-notes.md"})
        return written["release-notes.md"]

    def test_platform_selection_stays_within_dispatch_input_limit(self):
        input_block = self.workflow.split("permissions:", 1)[0]
        inputs = re.findall(r"^      [a-z][a-z0-9_]*:\s*$", input_block, re.MULTILINE)
        self.assertLessEqual(len(inputs), 10)
        self.assertIn("      platforms:\n", input_block)
        self.assertNotIn("platform_windows_x64", input_block)

    def test_release_jobs_use_the_pinned_rust_toolchain(self):
        self.assertNotIn("dtolnay/rust-toolchain@stable", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("dtolnay/rust-toolchain@1.97.0"),
            5,
        )

    def test_published_macos_bundles_require_developer_id_and_gatekeeper_checks(self):
        self.assertIn("MACOS_ENABLED: ${{ contains(steps.platforms.outputs.selected_platforms, 'macos-') }}", self.workflow)
        for secret in (
            "APPLE_CERTIFICATE",
            "APPLE_CERTIFICATE_PASSWORD",
            "APPLE_SIGNING_IDENTITY",
            "APPLE_ID",
            "APPLE_PASSWORD",
            "APPLE_TEAM_ID",
        ):
            self.assertIn(f"{secret}: ${{{{ secrets.{secret} }}}}", self.workflow)
        self.assertIn('bundle["macOS"] = {"signingIdentity": identity}', self.workflow)
        self.assertGreaterEqual(self.workflow.count("codesign --verify --deep --strict"), 2)
        self.assertGreaterEqual(self.workflow.count('test -d "${app_path}/Contents/_CodeSignature"'), 2)
        self.assertGreaterEqual(self.workflow.count("spctl --assess --type execute"), 2)

    def test_unsigned_macos_actions_do_not_receive_empty_apple_credentials(self):
        self.assertEqual(
            self.workflow.count("Export Apple signing credentials for Tauri"),
            2,
        )
        for step_name in (
            "Build, sign updater artifacts and upload",
            "Cross-build, sign updater artifacts and upload",
        ):
            section = self.workflow.split(f"- name: {step_name}", 1)[1]
            section = section.split("\n      - name:", 1)[0]
            self.assertNotIn("APPLE_CERTIFICATE:", section)
            self.assertNotIn("APPLE_ID:", section)
        self.assertIn('>> "${GITHUB_ENV}"', self.workflow)

    def test_private_source_checkouts_do_not_persist_credentials(self):
        private_checkouts = self.workflow.count(
            "token: ${{ secrets.PRIVATE_SOURCE_TOKEN }}"
        )
        self.assertEqual(private_checkouts, 6)
        self.assertEqual(
            self.workflow.count("persist-credentials: false"),
            private_checkouts,
        )

    def test_private_source_builds_do_not_use_public_actions_cache(self):
        self.assertNotIn("Swatinem/rust-cache", self.workflow)
        self.assertNotIn("actions/cache", self.workflow)

    def test_workflow_artifacts_have_a_short_retention_window(self):
        self.assertEqual(self.workflow.count("retention-days: 7"), 2)

    def test_finalization_normalizes_and_rechecks_updater_metadata(self):
        self.assertIn("scripts/finalize-release.py", self.workflow)
        self.assertNotIn("releases/tags/${TAG_NAME}", self.workflow)
        self.assertIn("release_highlights:", self.workflow)
        self.assertIn("--highlights-file release-highlights.md", self.workflow)

    def test_draft_bootstrap_links_every_mobile_artifact(self):
        for architecture in ("arm64-v8a", "armeabi-v7a", "x86_64", "universal"):
            self.assertIn(architecture, self.workflow)
        self.assertIn("apk_v7", self.workflow)
        self.assertIn("apk_x86", self.workflow)
        self.assertIn("ios_ipa", self.workflow)
        self.assertIn("if ios_ipa:", self.workflow)
        self.assertIn("无签名 IPA（侧载安装）", self.workflow)
        self.assertIn(
            'for marker in ("arm64-v8a", "armeabi-v7a", "x86_64")',
            self.workflow,
        )

    def test_draft_bootstrap_renders_every_mobile_download_link(self):
        assets = [
            "fanqie-android-arm64-v8a.apk",
            "fanqie-android-armeabi-v7a.apk",
            "fanqie-android-x86_64.apk",
            "fanqie-android-universal.apk",
            "fanqie-android.aab",
            "fanqie-ios-arm64.ipa",
        ]
        notes = self.render_draft_notes(assets)
        base = (
            "https://github.com/POf-L/Fanqie-novel-Downloader/"
            "releases/download/vprevious/"
        )

        for asset in assets:
            self.assertIn(f"({base}{asset})", notes)
        self.assertIn("32位 armeabi-v7a", notes)
        self.assertIn("模拟器 x86_64", notes)
        self.assertIn("无签名 IPA（侧载安装）", notes)

    def test_draft_bootstrap_does_not_mislabel_split_apk_as_universal(self):
        notes = self.render_draft_notes(
            [
                "fanqie-android-arm64-v8a.apk",
                "fanqie-android-armeabi-v7a.apk",
                "fanqie-android-x86_64.apk",
            ]
        )

        self.assertNotIn("通用版 universal", notes)

    def test_draft_recovery_reuses_the_finalizer_without_rebuilding(self):
        self.assertIn("name: Finalize Draft Release", self.finalize_workflow)
        self.assertIn("permissions:\n  contents: write", self.finalize_workflow)
        self.assertIn("scripts/finalize-release.py", self.finalize_workflow)
        self.assertIn("source_commit:", self.finalize_workflow)
        self.assertNotIn("tauri-apps/tauri-action", self.finalize_workflow)
        self.assertNotIn("PRIVATE_SOURCE_REPOSITORY", self.finalize_workflow)

    def test_finalizer_fetches_drafts_by_database_id(self):
        self.assertIn('"databaseId,tagName"', self.finalizer)
        self.assertIn('f"repos/{repo}/releases/{database_id}"', self.finalizer)
        self.assertIn('"--paginate"', self.finalizer)
        self.assertIn('"--slurp"', self.finalizer)
        self.assertNotIn("releases/tags/", self.finalizer)

    def test_wrapper_has_automatic_tooling_validation(self):
        self.assertIn("pull_request:", self.ci_workflow)
        self.assertIn("python -m unittest discover", self.ci_workflow)
        self.assertIn("rhysd/actionlint:1.7.7", self.ci_workflow)

    def test_repair_workflow_reuses_normalizer_and_updates_checksums(self):
        self.assertIn("name: Repair Updater Metadata", self.repair_workflow)
        self.assertIn("permissions:\n  contents: write", self.repair_workflow)
        self.assertIn("scripts/normalize-updater-metadata.py", self.repair_workflow)
        self.assertIn("--check", self.repair_workflow)
        self.assertIn("SHA256SUMS-release.txt", self.repair_workflow)
        self.assertIn('gh release upload "${tag}"', self.repair_workflow)


if __name__ == "__main__":
    unittest.main()
