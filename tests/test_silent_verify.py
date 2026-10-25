import os
import re
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
    "checklist-sync",
    "fmt",
    "clippy-desktop",
    "clippy-default",
    "clippy-cli",
    "test-desktop",
    "test-cli",
    "node-test",
    "node-check",
    "diff-check",
]


def checks_block():
    """silent-verify.sh 里的 checks=( ... ) 原文，用来伪造一份一致的 verify-local.sh。"""
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"^checks=\(\n.*?^\)\n", text, re.M | re.S)
    assert match, "silent-verify.sh 缺少 checks=( ... ) 清单"
    return match.group(0)


class SilentVerifyTest(unittest.TestCase):
    """用假的 cargo/node/git 跑 silent-verify.sh：它们会打印假的测试名、依赖和源码片段，
    断言这些内容一个字都不会出现在脚本的 stdout/stderr（也就是公开日志）里。"""

    def run_script(self, failing="", local_checks=None, github_output=False):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / "private-src"
            (source / "tests").mkdir(parents=True)
            (source / "tests" / "a.js").write_text("", encoding="utf-8")
            if local_checks is None:
                local_checks = checks_block()
            if local_checks:
                (source / "scripts").mkdir()
                (source / "scripts" / "verify-local.sh").write_text(
                    "#!/usr/bin/env bash\nset -uo pipefail\n\n" + local_checks + "\necho done\n",
                    encoding="utf-8",
                )
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
            env.pop("GITHUB_OUTPUT", None)
            output_file = tmp / "github-output"
            if github_output:
                env["GITHUB_OUTPUT"] = str(output_file)
            result = subprocess.run(
                ["bash", str(SCRIPT), str(source)],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            leftovers = list(runner_temp.iterdir())
            outputs = output_file.read_text(encoding="utf-8") if github_output else ""
        if github_output:
            return result, leftovers, outputs
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
        self.assertIn("verify 全部通过（9 项）", result.stdout)
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

    def test_cargo_checks_use_locked(self):
        block = checks_block()
        cargo_lines = [line for line in block.splitlines() if "|cargo " in line]
        self.assertEqual(len(cargo_lines), 6)
        for line in cargo_lines:
            if "cargo fmt" in line:
                continue
            self.assertIn(" --locked ", line)

    def test_checklist_drift_fails_without_printing_private_script(self):
        drifted = checks_block().replace("cargo test --locked", "cargo test", 1)
        result, _ = self.run_script(local_checks=drifted)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(result.stdout, r"失败  checklist-sync\s+退出码 1")
        self.assertRegex(result.stdout, r"通过  test-desktop\s+退出码 0")
        self.assertIn("检查清单不一致", result.stdout)
        self.assertEqual(result.stdout.count("::error::"), 1)

    def test_missing_local_script_fails_checklist_sync(self):
        result, _ = self.run_script(local_checks="")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"失败  checklist-sync")

    def test_writes_summary_for_release_notes(self):
        result, _, outputs = self.run_script(github_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("passed=9\n", outputs)
        self.assertIn("total=9\n", outputs)
        self.assertIn("summary=verify 9/9 通过\n", outputs)
        result, _, outputs = self.run_script(failing="cli", github_output=True)
        self.assertIn("passed=7\n", outputs)


if __name__ == "__main__":
    unittest.main()
