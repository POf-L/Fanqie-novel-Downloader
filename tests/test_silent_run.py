import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "silent-run.mjs"
NODE = shutil.which("node")
if NODE:
    # node 可能是版本管理器的 shim，会往 PATH 前面加自己的 bin 目录（里面可能有真的
    # tauri / npm）；直接用真实的 node 可执行文件。
    NODE = subprocess.run(
        [NODE, "-p", "process.execPath"], capture_output=True, text=True, check=True
    ).stdout.strip()

# 替身会打印的内容：私有 crate 名、链接命令里的依赖清单、依赖下载/编译行、
# 测试名和源码片段。任何一个出现在 silent-run 的 stdout/stderr（公开日志）里都算泄露。
LEAKS = [
    "fanqie_account_auth",
    "PRIVATE_SECRET_MARKER",
    "Compiling ",
    "Downloaded ",
    "::tests::",
    "test result:",
    "libsecret_dep_9f3a",
    "read_private_token",
]
FAKE_BUILD = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    echo "  Downloaded secret_dep_9f3a v0.4.2"
    echo "   Compiling fanqie_account_auth v0.1.0 (/private-src/src-tauri/account-auth)"
    echo "test backend::PRIVATE_SECRET_MARKER::tests::login ... ok"
    echo "test result: ok. 688 passed"
    echo 'error: linking with `aarch64-linux-gnu-gcc` failed: exit status: 1' >&2
    echo '  = note: "aarch64-linux-gnu-gcc" "/tmp/deps/libfanqie_account_auth-0123.rlib" "/tmp/deps/libsecret_dep_9f3a-77.rlib" "-lglib-2.0"' >&2
    echo 'src/account.rs:12:  let token = read_private_token();' >&2
    echo "::error::PRIVATE_SECRET_MARKER"
    echo "$0 $*" >> "$CALLS"
    if [[ -n "${FAIL_MATCH:-}" && " $* " == *" ${FAIL_MATCH} "* ]]; then exit 101; fi
    exit 0
    """
)


@unittest.skipIf(NODE is None, "需要 node")
class SilentRunTest(unittest.TestCase):
    """用会打印假依赖清单 / 私有 crate 名 / 源码的替身跑 silent-run.mjs，确认这些内容
    一个字都不进公开日志，只留通过/失败、退出码、用时和本地复现提示，且本地日志被删。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.runner_temp = self.tmp / "runner-temp"
        self.runner_temp.mkdir()
        self.calls = self.tmp / "calls.txt"
        self.calls.write_text("", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def fake(self, name, body=FAKE_BUILD):
        path = self.bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def run_script(self, *args, fail_match="", extra_env=None):
        env = dict(os.environ)
        # 只留替身目录和系统目录（node 用绝对路径启动），确保不会碰到本机真实的
        # cargo / tauri / npm。
        env["PATH"] = os.pathsep.join([str(self.bin), "/usr/bin", "/bin"])
        env["RUNNER_TEMP"] = str(self.runner_temp)
        env["CALLS"] = str(self.calls)
        env["FAIL_MATCH"] = fail_match
        env.update(extra_env or {})
        result = subprocess.run(
            [NODE, str(SCRIPT), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result, result.stdout + result.stderr

    def assert_no_leak(self, output):
        for leak in LEAKS:
            self.assertNotIn(leak, output)
        self.assertEqual(list(self.runner_temp.iterdir()), [], "本地日志应在结束时删掉")

    def test_success_prints_only_status_code_and_duration(self):
        self.fake("cargo")
        result, output = self.run_script(
            "--name", "android-build", "--", "cargo", "tauri", "android", "build", "--apk"
        )
        self.assertEqual(result.returncode, 0, output)
        self.assert_no_leak(output)
        self.assertRegex(result.stdout.strip(), r"^通过  android-build\s+退出码 0\s+用时 \d+s$")
        self.assertIn("tauri android build --apk", self.calls.read_text(encoding="utf-8"))

    def test_link_failure_is_summarised_with_local_repro_hint(self):
        self.fake("cargo")
        result, output = self.run_script(
            "--name", "ios-build-unsigned", "--", "cargo", "tauri", "ios", "build", "--no-sign",
            fail_match="--no-sign",
        )
        self.assertEqual(result.returncode, 101, output)
        self.assert_no_leak(output)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 2, output)
        self.assertRegex(lines[0], r"^失败  ios-build-unsigned\s+退出码 101\s+用时 \d+s$")
        self.assertTrue(lines[1].startswith("::error::ios-build-unsigned 未通过（退出码 101）"))
        self.assertIn('请在私有仓库本地运行 "cargo tauri ios build --no-sign" 复现', lines[1])
        self.assertEqual(result.stderr, "")

    def test_tauri_action_script_mode_hides_build_output(self):
        self.fake("tauri")
        args = [
            "--tauri", "build", "--target", "aarch64-unknown-linux-gnu",
            "--bundles", "deb", "--config", "src-tauri/tauri.release.conf.json",
        ]
        result, output = self.run_script(*args)
        self.assertEqual(result.returncode, 0, output)
        self.assert_no_leak(output)
        self.assertNotIn("tauri-cli-check", result.stdout)
        self.assertRegex(result.stdout, r"通过  tauri-build-aarch64-unknown-linux-gnu\s+退出码 0")
        self.assertNotIn("tauri-cli-install", result.stdout)

        result, output = self.run_script(*args, fail_match="deb")
        self.assertEqual(result.returncode, 101, output)
        self.assert_no_leak(output)
        self.assertRegex(result.stdout, r"失败  tauri-build-aarch64-unknown-linux-gnu\s+退出码 101")
        self.assertIn(
            '"cargo tauri build --target aarch64-unknown-linux-gnu --bundles deb '
            '--config src-tauri/tauri.release.conf.json" 复现',
            result.stdout,
        )

    def test_tauri_cli_is_installed_quietly_when_missing(self):
        # 和 tauri-action 默认行为一致：没有 tauri 时 npm install -g @tauri-apps/cli@v2。
        # 假 npm 也会打印私有内容，并把假 tauri 装进 PATH。
        npm = FAKE_BUILD.replace(
            'echo "$0 $*" >> "$CALLS"',
            'echo "$0 $*" >> "$CALLS"\n'
            f'cp "{self.bin}/tauri-template" "{self.bin}/tauri"; chmod +x "{self.bin}/tauri"',
        )
        self.fake("npm", npm)
        self.fake("tauri-template")
        result, output = self.run_script("--tauri", "build", "--target", "x86_64-apple-darwin")
        self.assertEqual(result.returncode, 0, output)
        self.assert_no_leak(output)
        self.assertNotIn("tauri-cli-check", result.stdout)
        self.assertNotIn("失败", result.stdout)
        self.assertRegex(result.stdout, r"通过  tauri-cli-install\s+退出码 0")
        self.assertRegex(result.stdout, r"通过  tauri-build-x86_64-apple-darwin\s+退出码 0")
        self.assertNotIn("::error::", result.stdout)
        self.assertIn("install -g @tauri-apps/cli@v2", self.calls.read_text(encoding="utf-8"))

    def test_heartbeat_and_missing_command_do_not_leak(self):
        self.fake("cargo", FAKE_BUILD.replace("exit 0\n", "sleep 1\nexit 0\n"))
        result, output = self.run_script(
            "--name", "slow", "--", "cargo", "build",
            extra_env={"SILENT_RUN_HEARTBEAT_MS": "200"},
        )
        self.assertEqual(result.returncode, 0, output)
        self.assert_no_leak(output)
        self.assertIn("… slow 仍在运行", result.stdout)

        result, output = self.run_script("--name", "missing", "--", "does-not-exist-xyz")
        self.assertEqual(result.returncode, 127, output)
        self.assert_no_leak(output)
        self.assertRegex(result.stdout, r"失败  missing\s+退出码 127")

    def test_bad_usage_fails_closed(self):
        result, output = self.run_script("--name", "x")
        self.assertEqual(result.returncode, 2, output)
        result, output = self.run_script("--tauri")
        self.assertEqual(result.returncode, 2, output)
        self.assertEqual(list(self.runner_temp.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
