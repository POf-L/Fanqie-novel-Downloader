import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "silent-verify.sh"
SECRET = "PRIVATE_SECRET_MARKER"
EXPECTED_CHECKS = [
    "fmt",
    "clippy-desktop",
    "clippy-cli",
    "test-desktop",
    "test-cli",
    "node-test",
    "node-check",
    "diff-check",
]


class SilentVerifyTest(unittest.TestCase):
    """用假的 cargo/node/git 跑 silent-verify.sh：它们会打印假的测试名、依赖和源码片段，
    断言这些内容一个字都不会出现在脚本的 stdout/stderr（也就是公开日志）里。"""

    def run_script(self, failing=""):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / "private-src"
            (source / "tests").mkdir(parents=True)
            (source / "tests" / "a.js").write_text("", encoding="utf-8")
            fake_bin = tmp / "bin"
            fake_bin.mkdir()
            runner_temp = tmp / "runner-temp"
            runner_temp.mkdir()
            fake = textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                echo "   Compiling {SECRET}-crate v1.0.0"
                echo "test backend::{SECRET}::tests::login ... ok"
                echo "src/{SECRET}.rs:12: let token = read_secret();" >&2
                echo "::error::{SECRET}"
                case " $* " in
                  *" $FAIL_MATCH "*) exit 101 ;;
                esac
                exit 0
                """
            )
            for name in ("cargo", "node", "git"):
                path = fake_bin / name
                path.write_text(fake, encoding="utf-8")
                path.chmod(path.stat().st_mode | stat.S_IEXEC)
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            env["RUNNER_TEMP"] = str(runner_temp)
            env["FAIL_MATCH"] = failing or "__never__"
            result = subprocess.run(
                ["bash", str(SCRIPT), str(source)],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            leftovers = list(runner_temp.iterdir())
        return result, leftovers

    def test_success_prints_only_names_codes_and_durations(self):
        result, leftovers = self.run_script()
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn(SECRET, output)
        self.assertNotIn("Compiling", output)
        lines = [line for line in result.stdout.splitlines() if line.startswith("通过")]
        self.assertEqual([line.split()[1] for line in lines], EXPECTED_CHECKS)
        for line in lines:
            self.assertRegex(line, r"退出码 0\s+用时 \d+s$")
        self.assertIn("verify 全部通过（8 项）", result.stdout)
        self.assertEqual(leftovers, [], "本地日志应在结束时删掉")

    def test_failure_names_the_check_and_points_to_local_repro(self):
        # --bin fanqie 只出现在 CLI 的 clippy / test 两项里。
        result, leftovers = self.run_script(failing="cli")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, output)
        self.assertNotIn(SECRET, output)
        self.assertRegex(result.stdout, r"失败  clippy-cli\s+退出码 101")
        self.assertRegex(result.stdout, r"失败  test-cli\s+退出码 101")
        self.assertRegex(result.stdout, r"通过  test-desktop\s+退出码 0")
        self.assertIn("scripts/verify-local.sh clippy-cli", result.stdout)
        self.assertIn("scripts/verify-local.sh test-cli", result.stdout)
        self.assertEqual(result.stdout.count("::error::"), 2)
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
