import io
import json
import os
import re
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


TAURI_ACTION_USES = "uses: tauri-apps/tauri-action@1deb371b0cd8bd54025b384f1cd735e725c4060f # v1.0.0"

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-release.yml"
MAINTENANCE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "release-maintenance.yml"
)
FINALIZER = ROOT / "scripts" / "finalize-release.py"
UNSIGNED_FINALIZER = ROOT / "scripts" / "finalize-unsigned-release.py"
UNSIGNED_APPEND_FINALIZER = ROOT / "scripts" / "append-unsigned-finalizer.py"
STABLE_PUBLISHER = ROOT / "scripts" / "publish-stable-channel.py"
ASSET_AUDITOR = ROOT / "scripts" / "audit-release-assets.py"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.maintenance_workflow = MAINTENANCE_WORKFLOW.read_text(
            encoding="utf-8"
        )
        cls.finalizer = FINALIZER.read_text(encoding="utf-8")
        cls.unsigned_finalizer = UNSIGNED_FINALIZER.read_text(encoding="utf-8")
        cls.unsigned_append_finalizer = UNSIGNED_APPEND_FINALIZER.read_text(
            encoding="utf-8"
        )
        cls.stable_publisher = STABLE_PUBLISHER.read_text(encoding="utf-8")
        cls.asset_auditor = ASSET_AUDITOR.read_text(encoding="utf-8")
        cls.ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def render_draft_notes(self, asset_names, *, unsigned=False, unsigned_release=False):
        script = self.workflow.split("          python - <<'PY'\n", 1)[1]
        script = textwrap.dedent(script.split("\n          PY", 1)[0])
        releases = [
            {
                "draft": False,
                "tag_name": "vprevious",
                "name": "Previous release",
                "assets": [
                    {"name": "latest.json"},
                    {"name": "Fanqie-signed.exe.sig"},
                    *[{"name": name} for name in asset_names],
                ],
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
            try:
                exec(compile(script, str(WORKFLOW), "exec"), {})
            except SystemExit as error:
                self.assertEqual(error.code, 0)

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

    def test_unsigned_releases_keep_updater_signing_and_os_signing_is_separate(self):
        self.assertIn("update_channel=unsigned", self.workflow)
        self.assertIn(
            "Unsigned releases require TAURI_SIGNING_PRIVATE_KEY", self.workflow
        )
        self.assertEqual(
            self.workflow.count(
                "CREATE_UPDATER_ARTIFACTS: "
                "${{ needs.prepare.outputs.create_updater_artifacts }}"
            ),
            8,
        )
        self.assertEqual(
            self.workflow.count(
                "uploadUpdaterJson: ${{ needs.prepare.outputs.create_updater_artifacts == 'true' }}"
            ),
            2,
        )
        self.assertEqual(
            self.workflow.count(
                "uploadUpdaterSignatures: ${{ needs.prepare.outputs.create_updater_artifacts == 'true' }}"
            ),
            2,
        )
        self.assertGreaterEqual(
            self.workflow.count("TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}"),
            4,
        )
        self.assertEqual(
            self.workflow.count("Stage, sign and upload Windows portable executable"),
            2,
        )
        self.assertEqual(
            self.workflow.count(
                'npm install --global "@tauri-apps/cli@$env:TAURI_CLI_VERSION"'
            ),
            2,
        )
        self.assertEqual(
            self.workflow.count("tauri signer sign $portable"),
            2,
        )
        self.assertNotIn("cargo install tauri-cli --version $env:", self.workflow)
        # 移动端不能改用 npm 的 tauri：Gradle 的 rustBuild* 任务和 Xcode 的
        # "Build Rust Code" script phase 调用的是 cargo 子命令 `cargo tauri`，
        # 而 npm 全局安装不会提供 ~/.cargo/bin/cargo-tauri，会报
        # "no such command: tauri"。所以 Android / iOS 安装的是 tauri 官方
        # Release 的预编译 cargo-tauri（sha256 固定），拿不到时退回 cargo install。
        self.assertEqual(
            self.workflow.count(
                'bash "${GITHUB_WORKSPACE}/release-wrapper/scripts/install-cargo-tauri.sh"'
            ),
            2,
        )
        self.assertNotIn("cargo install tauri-cli", self.workflow)
        installer = (ROOT / "scripts" / "install-cargo-tauri.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'cargo install tauri-cli --version "${TAURI_CLI_VERSION}" --locked',
            installer,
        )
        self.assertIn("shasum -a 256 -c -", installer)
        self.assertIn('!= "tauri-cli ${version}"', installer)
        cli_version = re.search(
            r'TAURI_CLI_VERSION: "([0-9.]+)"', self.workflow
        ).group(1)
        # Android 跑在 ubuntu-latest（x86_64），iOS 跑在 macos-15（arm64）。
        for asset in (
            "cargo-tauri-x86_64-unknown-linux-gnu.tgz",
            "cargo-tauri-aarch64-apple-darwin.zip",
        ):
            self.assertRegex(
                installer,
                re.escape(f"{cli_version}/{asset})") + r"\n\s+echo \"[0-9a-f]{64}\"",
            )
        self.assertEqual(self.workflow.count('$signature = "$portable.sig"'), 2)
        self.assertIn("TAURI_CLI_VERSION: \"2.12.4\"", self.workflow)
        self.assertIn("ANDROID_KEYSTORE_BASE64: ${{ secrets.ANDROID_KEYSTORE_BASE64 }}", self.workflow)
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
            self.main_release_section().count(
                'codesign -dvv "${app_path}" 2>&1 | grep -Fqx "Signature=adhoc"'
            ),
            2,
        )
        self.assertNotIn(
            'test ! -d "${app_path}/Contents/_CodeSignature"', self.workflow
        )

    def test_unsigned_prerelease_uploads_release_assets_for_every_platform(self):
        release_enabled = (
            "inputs.publish_release == true || "
            "inputs.publish_unsigned_prerelease == true || "
            "inputs.publish_unsigned_release == true"
        )
        self.assertGreaterEqual(self.workflow.count(release_enabled), 2)
        self.assertEqual(
            self.main_release_section().count("uploadWorkflowArtifacts: false"), 2
        )
        self.assertNotIn("uploadWorkflowArtifacts: true", self.workflow)
        self.assertEqual(
            self.workflow.count(
                "releaseId: ${{ (inputs.publish_release || inputs.publish_unsigned_prerelease || inputs.publish_unsigned_release) && needs.prepare.outputs.create_updater_artifacts == 'true' && needs.release-bootstrap.outputs.release_id || '' }}"
            ),
            2,
        )
        self.assertEqual(
            self.workflow.count("- name: Upload unsigned desktop installers"),
            2,
        )
        # 两个桌面 job 都只按 release-bootstrap 给的 Release ID 上传。
        self.assertEqual(
            self.workflow.count(
                '                  sys.executable,\n'
                '                  uploader,\n'
                '                  "upload",\n'
                '                  *release_target,'
            ),
            2,
        )
        self.assertNotIn('"gh",\n                  "release",\n                  "upload"', self.workflow)
        self.assertEqual(self.workflow.count('single_directory(source / "macos", ".app")'), 2)
        self.assertGreaterEqual(self.workflow.count('stem = f"FanqieNovelDownloader-tauri-linux-{arch}"'), 2)
        self.assertEqual(
            self.workflow.count(
                'appimage_arch = "aarch64" if target.startswith("aarch64-") else "amd64"'
            ),
            2,
        )
        self.assertIn(
            '".nsis.zip", ".msi.zip", ".app.tar.gz", ".appimage.tar.gz"',
            self.workflow,
        )
        # AppImage 改名后重新签名，并清掉 tauri-action 上传的旧名资产。
        self.assertEqual(
            self.workflow.count(
                'appimage = output / f"FanqieNovelDownloader-tauri-{appimage_arch}.AppImage"'
            ),
            2,
        )
        self.assertEqual(
            self.workflow.count(
                'subprocess.run(["tauri", "signer", "sign", str(appimage)], check=True)'
            ),
            2,
        )
        self.assertNotIn('"delete-asset"', self.workflow)
        self.assertEqual(
            self.workflow.count(
                '                      uploader,\n'
                '                      "delete",\n'
                '                      *release_target,'
            ),
            2,
        )
        self.assertIn('r"unsigned-v[^/]+-r[1-9][0-9]*"', self.unsigned_finalizer)
        self.assertIn('expected="FanqieNovelDownloader-tauri-linux-${expected_arch}.deb"', self.workflow)
        # 预发布状态只由 release-bootstrap 建 Draft 时决定；tauri-action 不再建 Release。
        self.assertIn(
            "PRERELEASE: ${{ inputs.publish_unsigned_prerelease || inputs.prerelease }}",
            self.workflow,
        )

    def test_unsigned_finalizer_has_an_isolated_updater_channel_and_appends_guides(self):
        unsigned_job = self.workflow.split("\n  finalize-unsigned-release:\n", 1)[1]
        unsigned = self.unsigned_finalizer
        self.assertIn("scripts/finalize-unsigned-release.py", unsigned_job)
        self.assertIn(
            "Verify published device guide and unsigned updater channel", unsigned_job
        )
        self.assertIn("PLATFORMS: ${{ needs.prepare.outputs.selected_platforms }}", unsigned_job)
        self.assertIn("body.count(required[0]) != 1", unsigned_job)
        self.assertIn("platform_requirements", unsigned_job)
        signed_job = self.workflow.split("\n  finalize:\n", 1)[1].split(
            "\n  finalize-unsigned-release:\n", 1
        )[0]
        self.assertNotIn("finalize-unsigned-release.py", signed_job)
        self.assertNotIn("scripts/finalize-release.py", unsigned)
        self.assertIn("normalize-updater-metadata.py", unsigned)
        self.assertNotIn("--latest", unsigned)
        self.assertIn("SHA256SUMS-unsigned.txt", unsigned)
        self.assertIn('FORBIDDEN_EXACT = {"latest.json", "sha256sums-release.txt"}', unsigned)
        self.assertIn('".sig",', unsigned)
        self.assertIn('".msi.zip",', unsigned)
        self.assertIn("def require_asset(", unsigned)
        self.assertIn('"linux-x64": (', unsigned)
        self.assertIn('"Linux x64 DEB"', unsigned)
        self.assertIn("--draft=false", unsigned)
        self.assertIn("--prerelease", unsigned)
        self.assertIn("FINALIZER_START", unsigned)
        self.assertIn("DRAFT_START", unsigned)
        self.assertIn("def clean_draft_body", unsigned)
        self.assertIn("allow_legacy_draft", unsigned)
        self.assertIn("def append_finalizer", unsigned)
        self.assertIn("## 下载与安装", unsigned)
        self.assertIn("publish-unsigned-channel.py", unsigned)
        self.assertIn("prepare-release-artifacts.py", unsigned)
        self.assertIn("generate_finalizer_appendix", unsigned)
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
        self.assertIn('releases/tags/{alias_tag}', unsigned)

    def test_unsigned_draft_notes_warn_before_assets_finish(self):
        notes = self.render_draft_notes([], unsigned=True)
        self.assertIn("更新包仍由项目 updater 密钥校验", notes)
        self.assertIn("不会替代稳定版", notes)
        self.assertIn("`unsigned/latest.json`", notes)
        self.assertIn("未知发布者", notes)
        self.assertIn("Gatekeeper", notes)
        self.assertEqual(notes.count("<!-- fanqie:unsigned-draft:start -->"), 1)
        self.assertEqual(notes.count("<!-- fanqie:unsigned-draft:end -->"), 1)
        self.assertNotIn("releases/download/vprevious/", notes)
        self.assertNotIn("## 下载地址", notes)

    def test_unsigned_formal_release_is_latest_and_uses_isolated_updater_channel(self):
        input_block = self.workflow.split("permissions:", 1)[0]
        self.assertIn("      publish_unsigned_release:\n", input_block)
        self.assertIn(
            "publish_unsigned_release requires publish_release=true.", self.workflow
        )
        self.assertIn('"make_latest": "true"', self.unsigned_finalizer)
        self.assertIn('published.get("prerelease")', self.unsigned_finalizer)
        self.assertIn("inputs.publish_unsigned_release == true", self.workflow)
        notes = self.render_draft_notes([], unsigned_release=True)
        self.assertIn("支持经过 Minisign 校验的应用内更新", notes)
        self.assertIn("GitHub Latest", notes)
        self.assertIn("`unsigned/latest.json`", notes)
        self.assertNotIn("不会替代稳定版", notes)
        self.assertEqual(notes.count("<!-- fanqie:unsigned-draft:start -->"), 1)
        self.assertNotIn("releases/download/vprevious/", notes)
        self.assertNotIn("## 下载地址", notes)

    def test_failed_release_keeps_the_draft_for_maintenance(self):
        self.assertNotIn("cleanup-failed-draft:", self.workflow)
        self.assertNotIn('gh release delete "${TAG_NAME}"', self.workflow)

    def test_unsigned_draft_recovery_reuses_the_unsigned_finalizer(self):
        workflow = self.maintenance_workflow
        self.assertIn("name: 发布 / 维护工具", workflow)
        self.assertIn("finalize-unsigned-draft", workflow)
        self.assertIn("scripts/finalize-unsigned-release.py", workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertNotIn("PRIVATE_SOURCE_REPOSITORY", workflow)
        self.assertNotIn("tauri-apps/tauri-action", workflow)
        self.assertIn("rewrite-release-notes", workflow)
        self.assertIn("scripts/rewrite-release-notes.py", workflow)
        self.assertIn("refresh-unsigned-channel", workflow)
        self.assertIn("scripts/publish-unsigned-channel.py", workflow)
        self.assertIn("append-unsigned-finalizer", workflow)
        self.assertIn("scripts/append-unsigned-finalizer.py", workflow)
        self.assertIn("append-unsigned-finalizer only handles a published Release", self.unsigned_append_finalizer)
        self.assertIn("finalizer.append_finalizer", self.unsigned_append_finalizer)
        self.assertIn("--allow-legacy-draft", workflow)
        self.assertIn("scripts/merge-unsigned-draft-notes.py", self.workflow)

    def test_release_jobs_use_the_pinned_rust_toolchain(self):
        self.assertNotIn("dtolnay/rust-toolchain@stable", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("dtolnay/rust-toolchain@f08ac54821369508305fcb9e0121ec6e30ae9ada # 1.97.0"),
            5,
        )

    def run_android_signer_check(self, mode, digests):
        """运行 Android 收集步骤里的签名校验片段，apksigner 用假的替代。"""
        import subprocess
        import tempfile

        android_job = self.workflow.split("\n  android:\n", 1)[1].split(
            "\n  ios:\n", 1
        )[0]
        step = android_job.split("- name: Collect and verify signed Android artifacts\n", 1)[1]
        step = step.split("\n      - name: ", 1)[0]
        body = step.split('          APKSIGNER="', 1)[1]
        body = '          APKSIGNER="' + body.split("} > dist/android/SIGNING.txt", 1)[0]
        body += "} > dist/android/SIGNING.txt\n"
        expected = re.search(
            r'(?m)^  ANDROID_RELEASE_SIGNER_SHA256: "([0-9a-f]{64})"$', self.workflow
        ).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = root / "sdk" / "build-tools" / "36.0.0"
            tools.mkdir(parents=True)
            fake = tools / "apksigner"
            lines = "".join(
                f"echo 'Signer #{i} certificate SHA-256 digest: {d}'\n"
                for i, d in enumerate(digests, 1)
            )
            fake.write_text("#!/usr/bin/env bash\necho Verifies\n" + lines, encoding="utf-8")
            fake.chmod(0o755)
            (root / "dist" / "android").mkdir(parents=True)
            (root / "dist" / "android" / "app-arm64-v8a.apk").write_bytes(b"apk")
            env = dict(
                os.environ,
                ANDROID_HOME=str(root / "sdk"),
                ANDROID_BUILD_TOOLS="36.0.0",
                ANDROID_RELEASE_SIGNER_SHA256=expected,
                FANQIE_ANDROID_SIGNING_MODE=mode,
            )
            result = subprocess.run(
                ["bash", "-c", "set -euo pipefail\n" + textwrap.dedent(body)],
                cwd=root, env=env, capture_output=True, text=True,
            )
            signing = root / "dist" / "android" / "SIGNING.txt"
            text = signing.read_text(encoding="utf-8") if signing.exists() else ""
            return result, expected, text

    def test_android_release_apks_must_carry_the_pinned_signer(self):
        result, expected, signing = self.run_android_signer_check("release-secret", [])
        self.assertNotEqual(result.returncode, 0)
        ok, expected, signing = self.run_android_signer_check(
            "release-secret", [expected.upper()]
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn(f"signer_sha256={expected}", signing)
        wrong, _, _ = self.run_android_signer_check("release-secret", ["ab" * 32])
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("ANDROID_KEYSTORE_", wrong.stderr)
        extra, _, _ = self.run_android_signer_check(
            "release-secret", [expected, "cd" * 32]
        )
        self.assertNotEqual(extra.returncode, 0)

    def test_ci_internal_android_signing_only_warns(self):
        result, _, signing = self.run_android_signer_check("ci-internal", ["ab" * 32])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("::warning::", result.stdout)
        self.assertNotIn("signer_sha256=", signing)

    def test_android_setup_does_not_request_the_retired_tools_package(self):
        android_job = self.workflow.split("\n  android:\n", 1)[1].split(
            "\n  ios:\n", 1
        )[0]
        setup = android_job.split("- uses: android-actions/setup-android@9fc6c4e9069bf8d3d10b2204b1fb8f6ef7065407 # v3.2.2\n", 1)[1]
        setup = setup.split("\n      - ", 1)[0]
        self.assertIn("        with:\n", setup)
        packages = re.findall(r"^          packages: (.+)$", setup, re.MULTILINE)
        self.assertEqual(packages, ["platform-tools"])
        for package in (
            '"platforms;android-${ANDROID_API_LEVEL}"',
            '"build-tools;${ANDROID_BUILD_TOOLS}"',
            '"ndk;${ANDROID_NDK_VERSION}"',
        ):
            self.assertIn(package, android_job)

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

    def macos_unsigned_section(self):
        return self.workflow.split("  macos-unsigned-bootstrap:", 1)[1]

    def main_release_section(self):
        return self.workflow.split("  macos-unsigned-bootstrap:", 1)[0]

    def test_unsigned_macos_channel_never_enters_stable_updater_flow(self):
        self.assertIn("macos_unsigned_channel:", self.workflow)
        self.assertIn('tag_name = f"macos-unsigned-v{version}', self.workflow)
        # 独立通道与签名 / unsigned-v* 流程互斥：release-bootstrap 被跳过后
        # desktop / android / ios / finalize 全部不会运行。
        self.assertIn("if: inputs.macos_unsigned_channel != true", self.workflow)
        section = self.macos_unsigned_section()
        self.assertIn("--draft=false", section)
        self.assertGreaterEqual(section.count("--prerelease"), 2)
        self.assertIn("uploadUpdaterJson: false", section)
        self.assertIn("uploadUpdaterSignatures: false", section)
        self.assertIn('"createUpdaterArtifacts": False', section)
        self.assertIn("### 其他平台状态", section)
        self.assertIn("\\`apksigner\\`", section)
        self.assertNotIn("scripts/finalize-release.py", section)
        self.assertNotIn("--latest", section)
        self.assertIn("releases/tags/stable", section)
        # 该通道不需要 updater 签名密钥
        self.assertNotIn("TAURI_SIGNING_PRIVATE_KEY", section)

    def test_unsigned_macos_channel_builds_and_verifies_both_architectures(self):
        # 两种架构由 prepare 的固定矩阵驱动，不受 platforms 输入影响。
        for value in (
            '"os": "macos-15-intel",',
            '"macho_arch": "x86_64",',
            '"target": "x86_64-apple-darwin",',
            '"os": "macos-latest",',
            '"macho_arch": "arm64",',
            '"target": "aarch64-apple-darwin",',
        ):
            self.assertIn(value, self.workflow)
        section = self.macos_unsigned_section()
        for value in (
            "fromJSON(needs.prepare.outputs.macos_unsigned_matrix)",
            'test -d "${app_path}/Contents/_CodeSignature"',
            'codesign -dvv "${app_path}" 2>&1 | grep -Fqx "Signature=adhoc"',
            'test "${bundle_id}" = "com.pofl.fanqienoveldownloader"',
            'test "${bundle_version}" = "${APP_VERSION}"',
            'file "${executable}" | grep -F "${MACHO_ARCH}"',
            'hdiutil verify "${dmg_path}"',
            "hdiutil attach -readonly -nobrowse -mountpoint",
            'ditto "${mounted_app}" "${runtime_app}"',
            '"${runtime_executable}" >"${runtime_log}" 2>&1 &',
            'kill -0 "${runtime_pid}"',
            "for _ in {1..15}",
        ):
            self.assertIn(value, section)

        for arch in ("arm64", "x64"):
            for suffix in ("unsigned.dmg", "unsigned.zip"):
                self.assertIn(
                    f"FanqieNovelDownloader-macos-{arch}-{suffix}", section
                )
        self.assertIn("SHA256SUMS-macos-unsigned.txt", section)
        self.assertIn("sha256sum --check", section)

    def test_unsigned_macos_channel_keeps_private_source_out_of_artifacts(self):
        section = self.macos_unsigned_section()
        self.assertEqual(
            section.count("repository: ${{ env.PRIVATE_SOURCE_REPOSITORY }}"), 1
        )
        self.assertEqual(
            section.count("token: ${{ secrets.PRIVATE_SOURCE_TOKEN }}"), 1
        )
        # 私有源码检出一次，外加 bootstrap / build（silent-run）/ publish 三次 wrapper 检出。
        self.assertEqual(section.count("persist-credentials: false"), 4)
        upload_section = section.split(
            "- name: Upload unsigned macOS bundles", 1
        )[1].split("\n\n  macos-unsigned-publish:", 1)[0]
        self.assertIn("${{ runner.temp }}/unsigned-macos-", upload_section)
        self.assertNotIn("PRIVATE_SOURCE_PATH", upload_section)
        self.assertIn("retention-days: 7", upload_section)

    def test_private_source_checkouts_do_not_persist_credentials(self):
        private_checkouts = self.workflow.count(
            "token: ${{ secrets.PRIVATE_SOURCE_TOKEN }}"
        )
        self.assertEqual(private_checkouts, 7)
        checkouts = re.findall(
            r"uses: actions/checkout@[0-9a-f]{40} # v4[^\n]*\n        with:\n(?:          .*\n)+",
            self.workflow,
        )
        private = [block for block in checkouts if "PRIVATE_SOURCE_TOKEN" in block]
        self.assertEqual(len(private), private_checkouts)
        upload_wrappers = [block for block in checkouts if "sparse-checkout: scripts" in block]
        self.assertEqual(len(upload_wrappers), 6)
        for block in private + upload_wrappers:
            self.assertIn("persist-credentials: false", block)

    def _job_blocks(self):
        jobs_text = self.workflow.split("\njobs:\n", 1)[1]
        parts = re.split(r"(?m)^  ([A-Za-z0-9_-]+):\n", jobs_text)
        return dict(zip(parts[1::2], parts[2::2]))

    def test_private_builds_run_through_silent_runner(self):
        # 会编译私有源码的步骤（三处 tauri-action 和 Android / iOS 的 cargo tauri build）
        # 必须经过 scripts/silent-run.mjs：编译错误、链接命令（完整依赖清单、私有 crate
        # 名）和打包日志只写 runner 本地临时文件，不进公开日志。
        silent = "node ${{ github.workspace }}/release-wrapper/scripts/silent-run.mjs --tauri"
        steps = re.split(r"(?m)^      - ", self.workflow)
        tauri_steps = [step for step in steps if "uses: tauri-apps/tauri-action" in step]
        self.assertEqual(len(tauri_steps), 3)
        for step in tauri_steps:
            self.assertIn(f"tauriScript: {silent}", step)

        raw_builds = re.findall(r"(?m)^.*cargo tauri (?:android|ios) build.*$", self.workflow)
        self.assertEqual(len(raw_builds), 3)
        for line in raw_builds:
            self.assertRegex(line.strip(), r"^-- cargo tauri (android|ios) build")
        self.assertEqual(
            self.workflow.count('node "${GITHUB_WORKSPACE}/release-wrapper/scripts/silent-run.mjs"'),
            3,
        )
        for name in ("--name android-build", "--name ios-build-unsigned", "--name ios-build-app-store"):
            self.assertIn(name, self.workflow)

        # 每个用到 silent-run.mjs 的 job 都要先 checkout 公开仓库的 scripts。
        for job, block in self._job_blocks().items():
            if "silent-run.mjs" not in block:
                continue
            checkout = block.find("path: release-wrapper")
            self.assertNotEqual(checkout, -1, job)
            self.assertLess(checkout, block.find("silent-run.mjs"), job)
        self.assertTrue((ROOT / "scripts" / "silent-run.mjs").is_file())

    def test_linux_arm64_fallback_uses_multiarch_cross_environment(self):
        fallback = self._job_blocks()["desktop-fallback"]
        self.assertIn("run: bash release-wrapper/scripts/setup-linux-arm64-cross.sh", fallback)
        # 不再用宿主机 x64 的 WebKitGTK 开发包去链接 arm64 目标。
        self.assertNotIn("libwebkit2gtk-4.1-dev", fallback)
        script = (ROOT / "scripts" / "setup-linux-arm64-cross.sh").read_text(encoding="utf-8")
        for needle in (
            "dpkg --add-architecture arm64",
            "ports.ubuntu.com/ubuntu-ports",
            "libwebkit2gtk-4.1-dev:arm64",
            "libdbus-1-dev:arm64",
            "PKG_CONFIG_LIBDIR_${underscored}",
            "CARGO_TARGET_${upper}_LINKER",
        ):
            self.assertIn(needle, script)
        # 只输出环境变量和 apt 日志，不编译任何源码。
        self.assertNotIn("cargo ", script)
        self.assertNotIn("tauri ", script.replace("Tauri ", ""))

    def test_desktop_builds_run_in_parallel_with_latest_json_retries(self):
        # 桌面构建按 Draft ID 上传、附件名按平台区分，latest.json 由 finalize
        # 按实际附件重建，所以不再需要 max-parallel: 1 串行。
        self.assertNotIn("max-parallel", self.workflow)
        desktop = self.workflow.split("\n  desktop:\n", 1)[1].split(
            "\n  android:\n", 1
        )[0]
        self.assertEqual(desktop.count(TAURI_ACTION_USES), 2)
        self.assertEqual(desktop.count("retryAttempts: 5"), 2)
        self.assertIn(
            "metadata[\"platforms\"] = expected",
            (ROOT / "scripts" / "normalize-updater-metadata.py").read_text(
                encoding="utf-8"
            ),
        )

    def test_builds_overlap_verify_but_publishing_still_requires_it(self):
        # 桌面 / Android / iOS 和 verify 同时跑，只往不公开的 Draft 上传；
        # 真正发布的两个 finalize 必须显式要求 verify 成功。
        self.assertEqual(
            self.workflow.count("    needs: [prepare, release-bootstrap]\n"), 3
        )
        for job in ("finalize", "finalize-unsigned-release"):
            section = self.workflow.split(f"\n  {job}:\n", 1)[1].split(
                "\n    steps:\n", 1
            )[0]
            self.assertIn("verify", section.split("\n", 1)[0])
            self.assertIn("needs.verify.result == 'success' &&", section)
        fallback = self.workflow.split("\n  desktop-fallback:\n", 1)[1].split(
            "\n    strategy:\n", 1
        )[0]
        self.assertIn("needs.verify.result == 'success' &&", fallback)

    def test_verify_keeps_private_output_out_of_public_logs(self):
        # verify 仍在公开 runner 上跑，但所有私有检查的输出都只写 runner 本地
        # 临时文件：workflow 里不能直接出现 cargo/node 检查命令，apt 输出也要重定向。
        verify = self.workflow.split("\n  verify:\n", 1)[1].split(
            "\n  release-bootstrap:\n", 1
        )[0]
        self.assertIn(
            'bash release-wrapper/scripts/silent-verify.sh "${PRIVATE_SOURCE_PATH}"',
            verify,
        )
        for raw in ("cargo test", "cargo clippy", "cargo fmt", "node --test", "git diff --check"):
            self.assertNotIn(raw, verify)
        self.assertIn('</dev/null >"${log}" 2>&1', verify)
        self.assertNotIn("upload-artifact", verify)
        self.assertNotIn("set -x", verify)

    def test_prepare_runs_silent_third_party_license_gate(self):
        prepare = self.workflow.split("\n  prepare:\n", 1)[1].split("\n  verify:\n", 1)[0]
        self.assertIn("- name: Generate third-party license list (silent)", prepare)
        self.assertRegex(prepare, r'CARGO_ABOUT_SHA256: "[0-9a-f]{64}"')
        self.assertIn('>"${work}/log" 2>&1 </dev/null', prepare)
        self.assertIn(
            "third_party_licenses: ${{ steps.licenses.outputs.available }}", prepare
        )
        upload = prepare.split("- name: Upload third-party license list", 1)[1].split(
            "\n\n", 1
        )[0]
        # artifact 里只有生成的 HTML，不带私有源码。
        self.assertIn(
            "path: ${{ runner.temp }}/third-party-licenses/THIRD_PARTY_LICENSES.html",
            upload,
        )
        self.assertNotIn("PRIVATE_SOURCE_PATH", upload)
        self.assertIn("retention-days: 3", upload)

    def test_installers_and_release_ship_third_party_license_list(self):
        for job in ("desktop", "desktop-fallback", "android", "ios", "macos-unsigned-build"):
            section = self.workflow.split(f"\n  {job}:\n", 1)[1]
            section = re.split(r"\n  [a-z][a-z-]*:\n", section, maxsplit=1)[0]
            with self.subTest(job=job):
                self.assertIn("- name: Download third-party license list", section)
                self.assertIn(
                    "path: ${{ env.PRIVATE_SOURCE_PATH }}/src-tauri/licenses", section
                )
                self.assertIn("fanqie-third-party-licenses-placeholder", section)
        bootstrap = self.workflow.split("\n  release-bootstrap:\n", 1)[1].split(
            "\n  desktop:\n", 1
        )[0]
        self.assertIn(
            '"${RUNNER_TEMP}/third-party-licenses/THIRD_PARTY_LICENSES.html"', bootstrap
        )

    def test_published_release_requires_updater_signing_key(self):
        prepare = self.workflow.split("\n  prepare:\n", 1)[1].split("\n  verify:\n", 1)[0]
        self.assertIn(
            'if [[ "${PUBLISH_RELEASE}" == "true" && "${updater}" != "true" ]]; then',
            prepare,
        )

    def test_published_android_release_requires_official_keystore_up_front(self):
        self.assertIn(
            "FANQIE_ANDROID_REQUIRE_RELEASE_SIGNING: ${{ inputs.publish_release == true && 'true' || 'false' }}",
            self.workflow,
        )
        self.assertIn(
            "if: inputs.publish_release == true && steps.signing.outputs.mode != 'release-secret'",
            self.workflow,
        )

    def test_android_apks_get_16k_alignment_check_before_upload(self):
        check = self.workflow.index("- name: Check Android 16 KiB page alignment")
        collect = self.workflow.index("- name: Collect and verify signed Android artifacts")
        upload = self.workflow.index("- name: Upload Android release assets")
        self.assertLess(collect, check)
        self.assertLess(check, upload)
        self.assertIn("scripts/check-android-16k-alignment.py", self.workflow)

    def test_release_runs_are_never_cancelled_mid_publish(self):
        head = self.workflow.split("\njobs:\n", 1)[0]
        self.assertIn("cancel-in-progress: false", head)
        self.assertNotIn("cancel-in-progress: true", head)
        merge = (ROOT / ".github" / "workflows" / "maintenance-merge-drafts.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("cancel-in-progress: false", merge)

    def test_verify_summary_reaches_both_finalize_steps(self):
        verify = self.workflow.split("\n  verify:\n", 1)[1].split(
            "\n  release-bootstrap:\n", 1
        )[0]
        self.assertIn("summary: ${{ steps.silent_verify.outputs.summary }}", verify)
        self.assertIn("id: silent_verify", verify)
        self.assertEqual(
            self.workflow.count(
                "FANQIE_VERIFY_SUMMARY: ${{ needs.verify.outputs.summary }}"
            ),
            2,
        )

    def test_public_builds_quiet_cargo_and_rustc_warnings(self):
        def section(job, end):
            return self.workflow.split(f"\n  {job}:\n", 1)[1].split(f"\n  {end}:\n", 1)[0]

        append = 'echo "RUSTFLAGS=${RUSTFLAGS:+${RUSTFLAGS} }-Awarnings"'
        for job, end in (
            ("desktop", "desktop-fallback"),
            ("desktop-fallback", "android"),
            ("macos-unsigned-build", "macos-unsigned-publish"),
        ):
            body = section(job, end)
            self.assertEqual(body.count(append), 1, job)
            self.assertEqual(body.count('echo "CARGO_TERM_QUIET=true"'), 1, job)
        # 移动端不能设 RUSTFLAGS：会顶掉 cargo-mobile2 写的 target rustflags。
        for job, end in (("android", "ios"), ("ios", "finalize")):
            body = section(job, end)
            self.assertNotIn("RUSTFLAGS=", body, job)
            self.assertIn('echo "CARGO_TERM_QUIET=true" >> "${GITHUB_ENV}"', body)
        # 只追加，不在任何地方直接覆盖 RUSTFLAGS。
        self.assertNotRegex(self.workflow, r"\n\s+RUSTFLAGS:")

    def test_rust_cache_never_stores_private_build_outputs(self):
        # fork PR 的 workflow 能读 main 的缓存，所以缓存只放公开依赖的编译产物。
        self.assertNotIn("actions/cache", self.workflow)
        self.assertEqual(
            self.workflow.count(
                "uses: Swatinem/rust-cache@d1527c8f67ef9af357290475d4af4b0fab8f12e0 # v2.9.3"
            ),
            3,
        )
        self.assertEqual(self.workflow.count('cache-workspace-crates: "false"'), 3)
        self.assertEqual(
            self.workflow.count("save-if: ${{ github.ref == 'refs/heads/main' }}"), 3
        )
        self.assertNotIn("cache-on-failure", self.workflow)
        for job, nxt in (
            ("desktop", "desktop-fallback"),
            ("android", "ios"),
            ("ios", "finalize"),
        ):
            section = self.workflow.split(f"\n  {job}:\n", 1)[1].split(f"\n  {nxt}:\n", 1)[0]
            with self.subTest(job=job):
                self.assertIn("Swatinem/rust-cache@", section)
                last_step = section.rsplit("\n      - ", 1)[1]
                self.assertTrue(
                    last_step.startswith("name: Remove private build outputs before cache save")
                )
                self.assertIn("if: always()", last_step)
                self.assertIn("-name '*fanqie*'", last_step)
                self.assertIn('rm -rf "${target}"', last_step)

    def test_main_release_workflow_does_not_upload_workflow_artifacts(self):
        # 只允许两个 workflow artifact：macOS 未签名通道 build → publish 的交接
        # （只含 runner.temp 里的成品包，见 keeps_private_source_out_of_artifacts），
        # 以及 prepare 生成的第三方许可证清单（见 prepare_runs_silent_third_party_license_gate）。
        self.assertEqual(self.workflow.count("actions/upload-artifact"), 2)
        self.assertEqual(self.workflow.count("retention-days:"), 2)
        self.assertEqual(self.workflow.count("uploadWorkflowArtifacts: false"), 3)

    def test_finalization_normalizes_and_rechecks_updater_metadata(self):
        self.assertIn("scripts/finalize-release.py", self.workflow)
        self.assertNotIn("releases/tags/${TAG_NAME}", self.workflow)
        self.assertIn("release_highlights:", self.workflow)
        self.assertIn("--highlights-file release-highlights.md", self.workflow)
        self.assertIn("--signatures-dir", self.finalizer)
        self.assertIn("--signatures-dir", self.unsigned_finalizer)
        self.assertIn("--signatures-dir repair-check/signatures", self.maintenance_workflow)
        self.assertIn("audit-release-assets.py", self.finalizer)
        self.assertIn("audit-release-assets.py", self.unsigned_finalizer)
        self.assertIn("private-src", self.asset_auditor)
        self.assertIn('".map",', self.asset_auditor)
        self.assertIn('".pdb",', self.asset_auditor)
        self.assertIn('".rs",', self.asset_auditor)

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
        self.assertIn("rhysd/actionlint@sha256:", self.ci_workflow)
        self.assertIn("# 1.7.7", self.ci_workflow)

    def test_release_maintenance_combines_all_recovery_operations(self):
        workflow = self.maintenance_workflow
        input_block = workflow.split("permissions:", 1)[0]
        inputs = re.findall(r"^      [a-z][a-z0-9_]*:\s*$", input_block, re.MULTILINE)

        self.assertLessEqual(len(inputs), 10)
        for operation in (
            "finalize-signed-draft",
            "finalize-unsigned-draft",
            "append-unsigned-finalizer",
            "rewrite-release-notes",
            "refresh-stable-channel",
            "refresh-unsigned-channel",
            "repair-updater-metadata",
        ):
            self.assertIn(operation, workflow)
        self.assertIn("scripts/finalize-release.py", workflow)
        self.assertIn("scripts/finalize-unsigned-release.py", workflow)
        self.assertIn("scripts/publish-stable-channel.py", workflow)
        self.assertIn("scripts/publish-unsigned-channel.py", workflow)
        self.assertIn("scripts/rewrite-release-notes.py", workflow)
        self.assertIn("scripts/normalize-updater-metadata.py", workflow)
        self.assertIn("--check", workflow)
        self.assertIn("SHA256SUMS-release.txt", workflow)
        self.assertIn('gh release upload "${tag}"', workflow)

    def test_stable_publisher_filters_unsigned_and_alias_releases(self):
        self.assertIn("SIGNED_TAG_RE", self.stable_publisher)
        self.assertIn('release.get("prerelease") is False', self.stable_publisher)
        self.assertIn('METADATA_NAME in names', self.stable_publisher)
        self.assertIn('name.lower().endswith(".sig")', self.stable_publisher)
        self.assertIn('"make_latest": "false"', self.stable_publisher)
        self.assertIn('"target_commitish": target_commitish', self.stable_publisher)
        self.assertIn('"prerelease": True', self.stable_publisher)
        self.assertIn("Stable channel refreshed", self.stable_publisher)

    def test_actions_are_grouped_into_expected_active_workflows(self):
        workflow_names = {
            path.name for path in (ROOT / ".github" / "workflows").glob("*.yml")
        }
        self.assertEqual(
            workflow_names,
            {
                "build-release.yml",
                "ci.yml",
                "maintenance-merge-drafts.yml",
                "release-maintenance.yml",
            },
        )


class WorkflowHardeningTest(unittest.TestCase):
    """供应链与令牌最小化：所有 workflow 都要满足的硬性约束。"""

    WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

    def test_every_action_is_pinned_to_a_full_commit_sha(self):
        for path in self.WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"^\s*(?:-\s+)?uses:\s*(\S+)", text, re.MULTILINE):
                reference = match.group(1)
                with self.subTest(workflow=path.name, uses=reference):
                    if reference.startswith("./"):
                        continue
                    if reference.startswith("docker://"):
                        self.assertRegex(reference, r"@sha256:[0-9a-f]{64}$")
                    else:
                        self.assertRegex(reference, r"@[0-9a-f]{40}$")

    def test_every_checkout_drops_its_credentials(self):
        for path in self.WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            blocks = re.findall(
                r"uses: actions/checkout@\S+[^\n]*\n((?:        (?!- ).*\n|\s*\n)*)",
                text,
            )
            for block in blocks:
                with self.subTest(workflow=path.name):
                    self.assertIn("persist-credentials: false", block)

    def test_no_pull_request_target_trigger(self):
        for path in self.WORKFLOWS:
            self.assertNotIn("pull_request_target", path.read_text(encoding="utf-8"), path.name)

    def test_release_token_is_read_only_by_default_and_verify_never_writes(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        header = workflow.split("\njobs:\n", 1)[0]
        self.assertRegex(header, r"\npermissions:\n  contents: read\n")
        verify = workflow.split("\n  verify:\n", 1)[1].split("\n  release-bootstrap:\n", 1)[0]
        self.assertNotIn("contents: write", verify)

    def test_run_blocks_do_not_interpolate_expressions(self):
        for path in self.WORKFLOWS:
            lines = path.read_text(encoding="utf-8").splitlines()
            index = 0
            while index < len(lines):
                match = re.match(r"^(\s+)run: \|", lines[index])
                if not match:
                    index += 1
                    continue
                indent = len(match.group(1))
                index += 1
                while index < len(lines) and (
                    not lines[index].strip()
                    or len(lines[index]) - len(lines[index].lstrip()) > indent
                ):
                    with self.subTest(workflow=path.name, line=index + 1):
                        self.assertNotIn("${{", lines[index])
                    index += 1


if __name__ == "__main__":
    unittest.main()
