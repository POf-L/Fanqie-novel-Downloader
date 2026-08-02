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
UNSIGNED_MACOS_WORKFLOW = (
    ROOT / ".github" / "workflows" / "publish-unsigned-macos.yml"
)
MAINTENANCE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "release-maintenance.yml"
)
FINALIZER = ROOT / "scripts" / "finalize-release.py"
UNSIGNED_FINALIZER = ROOT / "scripts" / "finalize-unsigned-release.py"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.unsigned_macos_workflow = UNSIGNED_MACOS_WORKFLOW.read_text(
            encoding="utf-8"
        )
        cls.maintenance_workflow = MAINTENANCE_WORKFLOW.read_text(
            encoding="utf-8"
        )
        cls.finalizer = FINALIZER.read_text(encoding="utf-8")
        cls.unsigned_finalizer = UNSIGNED_FINALIZER.read_text(encoding="utf-8")
        cls.ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def render_draft_notes(self, asset_names, *, unsigned=False, unsigned_release=False):
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
            "PUBLISH_UNSIGNED_PRERELEASE": str(unsigned).lower(),
            "PUBLISH_UNSIGNED_RELEASE": str(unsigned_release).lower(),
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

    def test_unsigned_prerelease_has_an_explicit_exclusive_publish_mode(self):
        input_block = self.workflow.split("permissions:", 1)[0]
        self.assertIn("      publish_unsigned_prerelease:\n", input_block)
        unsigned_input = input_block.split(
            "      publish_unsigned_prerelease:\n", 1
        )[1].split("      prerelease:\n", 1)[0]
        self.assertIn("        default: false\n", unsigned_input)
        self.assertIn("        type: boolean\n", unsigned_input)
        self.assertIn(
            "publish_release and publish_unsigned_prerelease are mutually exclusive.",
            self.workflow,
        )
        self.assertIn('tag_name = f"unsigned-v{version}-r', self.workflow)
        self.assertIn('tag_name = f"v{version}"', self.workflow)

    def test_unsigned_prerelease_disables_updater_and_official_signing_inputs(self):
        self.assertIn("create_updater_artifacts=false", self.workflow)
        self.assertEqual(
            self.workflow.count(
                "CREATE_UPDATER_ARTIFACTS: "
                "${{ needs.prepare.outputs.create_updater_artifacts }}"
            ),
            2,
        )
        self.assertEqual(
            self.workflow.count(
                "uploadUpdaterJson: ${{ !inputs.publish_unsigned_prerelease && !inputs.publish_unsigned_release }}"
            ),
            2,
        )
        self.assertEqual(
            self.workflow.count(
                "uploadUpdaterSignatures: ${{ !inputs.publish_unsigned_prerelease && !inputs.publish_unsigned_release }}"
            ),
            2,
        )
        for secret in (
            "TAURI_SIGNING_PRIVATE_KEY",
            "TAURI_SIGNING_PRIVATE_KEY_PASSWORD",
            "APPLE_SIGNING_IDENTITY",
            "ANDROID_KEYSTORE_BASE64",
        ):
            self.assertIn(
                f"!inputs.publish_unsigned_prerelease && !inputs.publish_unsigned_release && secrets.{secret}",
                self.workflow,
            )
        self.assertIn(
            "inputs.publish_unsigned_prerelease == true || "
            "inputs.publish_unsigned_release == true || "
            "needs.prepare.outputs.ios_signing != 'true'",
            self.workflow,
        )
        self.assertEqual(
            self.workflow.count("- name: Verify unsigned macOS bundle"),
            2,
        )
        self.assertEqual(
            self.workflow.count(
                'test ! -d "${app_path}/Contents/_CodeSignature"'
            ),
            2,
        )

    def test_unsigned_prerelease_uploads_release_assets_for_every_platform(self):
        release_enabled = (
            "inputs.publish_release == true || "
            "inputs.publish_unsigned_prerelease == true || "
            "inputs.publish_unsigned_release == true"
        )
        self.assertGreaterEqual(self.workflow.count(release_enabled), 2)
        self.assertEqual(
            self.workflow.count(
                "!inputs.publish_unsigned_prerelease && !inputs.publish_unsigned_release && inputs.publish_release && needs.prepare.outputs.tag_name || ''"
            ),
            2,
        )
        self.assertEqual(
            self.workflow.count("- name: Upload unsigned desktop installers"),
            2,
        )
        self.assertEqual(
            self.workflow.count('"gh",\n                  "release",\n                  "upload"'),
            2,
        )
        self.assertEqual(self.workflow.count('single_directory(source / "macos", ".app")'), 2)
        self.assertGreaterEqual(self.workflow.count('stem = f"FanqieNovelDownloader-tauri-linux-{arch}"'), 2)
        self.assertIn(
            '".sig", ".nsis.zip", ".msi.zip", ".app.tar.gz", ".appimage.tar.gz"',
            self.workflow,
        )
        self.assertIn('r"unsigned-v[^/]+-r[1-9][0-9]*"', self.unsigned_finalizer)
        self.assertIn('expected="FanqieNovelDownloader-tauri-linux-${expected_arch}.deb"', self.workflow)
        self.assertIn(
            "prerelease: ${{ inputs.publish_unsigned_prerelease || inputs.prerelease }}",
            self.workflow,
        )

    def test_unsigned_finalizer_never_enters_stable_updater_channel(self):
        unsigned_job = self.workflow.split("\n  finalize-unsigned:\n", 1)[1]
        unsigned = self.unsigned_finalizer
        self.assertIn("scripts/finalize-unsigned-release.py", unsigned_job)
        self.assertNotIn("scripts/finalize-release.py", unsigned)
        self.assertNotIn("normalize-updater-metadata.py", unsigned)
        self.assertNotIn("--latest", unsigned)
        self.assertIn("SHA256SUMS-unsigned.txt", unsigned)
        self.assertIn('FORBIDDEN_EXACT = {"latest.json", "sha256sums-release.txt"}', unsigned)
        self.assertIn('".sig",', unsigned)
        self.assertIn('".msi.zip",', unsigned)
        self.assertIn("def require_asset(", unsigned)
        self.assertIn('"linux-x64": ("Linux x64", ("linux-amd64",), (".deb",))', unsigned)
        self.assertIn("--draft=false", unsigned)
        self.assertIn("--prerelease", unsigned)
        self.assertIn(
            "未签名版本，仅供测试，不支持自动更新",
            unsigned,
        )
        self.assertIn("未知发布者", unsigned)
        self.assertIn("Gatekeeper", unsigned)
        self.assertIn(
            'f"repos/{repo}/releases/latest"',
            unsigned,
        )
        self.assertIn(
            "if stable_after != stable_before:",
            unsigned,
        )
        self.assertIn('"databaseId,tagName"', unsigned)
        self.assertIn('f"repos/{repo}/releases/{database_id}"', unsigned)
        self.assertNotIn('releases/tags/', unsigned)

    def test_unsigned_draft_notes_warn_before_assets_finish(self):
        notes = self.render_draft_notes([], unsigned=True)
        self.assertIn("未签名版本，仅供测试，不支持自动更新", notes)
        self.assertIn("不会替代稳定版", notes)
        self.assertIn("不会生成或上传 `latest.json`", notes)
        self.assertIn("未知发布者", notes)
        self.assertIn("Gatekeeper", notes)

    def test_unsigned_formal_release_is_normal_but_stays_out_of_updater_channel(self):
        input_block = self.workflow.split("permissions:", 1)[0]
        self.assertIn("      publish_unsigned_release:\n", input_block)
        self.assertIn(
            "publish_unsigned_release requires publish_release=true.", self.workflow
        )
        self.assertIn('"make_latest": False', self.unsigned_finalizer)
        self.assertIn('published.get("prerelease")', self.unsigned_finalizer)
        self.assertIn("inputs.publish_unsigned_release == true", self.workflow)
        notes = self.render_draft_notes([], unsigned_release=True)
        self.assertIn("未签名版本，不支持自动更新", notes)
        self.assertIn("普通 GitHub Release", notes)
        self.assertIn("不会生成或上传 `latest.json`", notes)
        self.assertNotIn("不会替代稳定版", notes)

    def test_unsigned_draft_recovery_reuses_the_unsigned_finalizer(self):
        workflow = self.maintenance_workflow
        self.assertIn("name: 发布 / 维护工具", workflow)
        self.assertIn("finalize-unsigned-draft", workflow)
        self.assertIn("scripts/finalize-unsigned-release.py", workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertNotIn("PRIVATE_SOURCE_REPOSITORY", workflow)
        self.assertNotIn("tauri-apps/tauri-action", workflow)

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

    def test_unsigned_macos_channel_never_enters_stable_updater_flow(self):
        workflow = self.unsigned_macos_workflow
        self.assertIn("name: 发布 / macOS 未签名", workflow)
        self.assertIn('tag = f"macos-unsigned-v{version}', workflow)
        self.assertIn("--draft=false", workflow)
        self.assertGreaterEqual(workflow.count("--prerelease"), 2)
        self.assertIn("uploadUpdaterJson: false", workflow)
        self.assertIn("uploadUpdaterSignatures: false", workflow)
        self.assertIn('"createUpdaterArtifacts": False', workflow)
        self.assertIn("### 其他平台状态", workflow)
        self.assertIn("\\`apksigner\\`", workflow)
        self.assertNotIn("scripts/finalize-release.py", workflow)
        self.assertNotIn("--latest", workflow)
        self.assertIn(
            'releases/latest" --jq .tag_name)" = "${STABLE_TAG}"',
            workflow,
        )

    def test_unsigned_macos_channel_builds_and_verifies_both_architectures(self):
        workflow = self.unsigned_macos_workflow
        for value in (
            "macos-15-intel",
            "macos-latest",
            "x86_64-apple-darwin",
            "aarch64-apple-darwin",
            'test ! -d "${app_path}/Contents/_CodeSignature"',
            'test "${bundle_id}" = "com.pofl.fanqienoveldownloader"',
            'test "${bundle_version}" = "${APP_VERSION}"',
            'file "${executable}" | grep -F "${MACHO_ARCH}"',
            'hdiutil verify "${dmg_path}"',
            'hdiutil attach -readonly -nobrowse -mountpoint',
            'ditto "${mounted_app}" "${runtime_app}"',
            '"${runtime_executable}" >"${runtime_log}" 2>&1 &',
            'kill -0 "${runtime_pid}"',
            "for _ in {1..15}",
        ):
            self.assertIn(value, workflow)

        for arch in ("arm64", "x64"):
            for suffix in ("unsigned.dmg", "unsigned.zip"):
                self.assertIn(
                    f"FanqieNovelDownloader-macos-{arch}-{suffix}", workflow
                )
        self.assertIn("SHA256SUMS-macos-unsigned.txt", workflow)
        self.assertIn("sha256sum --check", workflow)

    def test_unsigned_macos_channel_keeps_private_source_out_of_artifacts(self):
        workflow = self.unsigned_macos_workflow
        private_checkouts = workflow.count(
            "repository: ${{ env.PRIVATE_SOURCE_REPOSITORY }}"
        )
        self.assertEqual(private_checkouts, 3)
        self.assertEqual(
            workflow.count("token: ${{ secrets.PRIVATE_SOURCE_TOKEN }}"),
            private_checkouts,
        )
        self.assertGreaterEqual(
            workflow.count("persist-credentials: false"), private_checkouts
        )
        self.assertNotIn("actions/cache", workflow)
        self.assertNotIn("Swatinem/rust-cache", workflow)
        upload_section = workflow.split(
            "- name: Upload unsigned macOS bundles", 1
        )[1].split("\n\n  publish:", 1)[0]
        self.assertIn("${{ runner.temp }}/unsigned-macos-", upload_section)
        self.assertNotIn("PRIVATE_SOURCE_PATH", upload_section)
        self.assertIn("retention-days: 7", upload_section)

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
        workflow = self.maintenance_workflow
        self.assertIn("name: 发布 / 维护工具", workflow)
        self.assertIn("finalize-signed-draft", workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertIn("scripts/finalize-release.py", workflow)
        self.assertIn("source_commit:", workflow)
        self.assertNotIn("tauri-apps/tauri-action", workflow)
        self.assertNotIn("PRIVATE_SOURCE_REPOSITORY", workflow)

    def test_finalizer_fetches_drafts_by_database_id(self):
        self.assertIn('"databaseId,tagName"', self.finalizer)
        self.assertIn('f"repos/{repo}/releases/{database_id}"', self.finalizer)
        self.assertIn('"--paginate"', self.finalizer)
        self.assertIn('"--slurp"', self.finalizer)
        self.assertNotIn("releases/tags/", self.finalizer)

    def test_wrapper_has_automatic_tooling_validation(self):
        self.assertIn("name: CI / 仓库校验", self.ci_workflow)
        self.assertIn("pull_request:", self.ci_workflow)
        self.assertEqual(self.ci_workflow.count("    paths-ignore:"), 2)
        for documentation_path in (
            '      - "README.md"',
            '      - "CONTRIBUTING.md"',
            '      - "SECURITY.md"',
            '      - "docs/**"',
        ):
            self.assertEqual(self.ci_workflow.count(documentation_path), 2)
        self.assertIn("python -m unittest discover", self.ci_workflow)
        self.assertIn("rhysd/actionlint:1.7.7", self.ci_workflow)

    def test_release_maintenance_combines_all_recovery_operations(self):
        workflow = self.maintenance_workflow
        input_block = workflow.split("permissions:", 1)[0]
        inputs = re.findall(r"^      [a-z][a-z0-9_]*:\s*$", input_block, re.MULTILINE)

        self.assertLessEqual(len(inputs), 10)
        for operation in (
            "finalize-signed-draft",
            "finalize-unsigned-draft",
            "repair-updater-metadata",
        ):
            self.assertIn(operation, workflow)
        self.assertIn("scripts/finalize-release.py", workflow)
        self.assertIn("scripts/finalize-unsigned-release.py", workflow)
        self.assertIn("scripts/normalize-updater-metadata.py", workflow)
        self.assertIn("--check", workflow)
        self.assertIn("SHA256SUMS-release.txt", workflow)
        self.assertIn('gh release upload "${tag}"', workflow)

    def test_actions_are_grouped_into_four_active_workflows(self):
        workflow_names = {
            path.name for path in (ROOT / ".github" / "workflows").glob("*.yml")
        }
        self.assertEqual(
            workflow_names,
            {
                "build-release.yml",
                "ci.yml",
                "publish-unsigned-macos.yml",
                "release-maintenance.yml",
            },
        )


if __name__ == "__main__":
    unittest.main()
