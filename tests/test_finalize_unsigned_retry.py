"""Tests for the release asset audit retry added after #727.

Issue #727 lost a finished build because `gh release download` received a
transient HTTP 500 while fetching the iOS ipa, and the audit had no retry. These
tests pin down which failures are retried and which must still fail fast.
"""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finalize-unsigned-release.py"
SPEC = importlib.util.spec_from_file_location("finalize_unsigned_release", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def failure(stderr: str = "", stdout: str = "") -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(
        returncode=1, cmd=["gh", "release", "download"], output=stdout, stderr=stderr
    )


class AssetDownloadRetryTest(unittest.TestCase):
    def test_transient_server_error_is_retried_until_it_succeeds(self):
        outcomes = [failure(stderr="HTTP 500 (https://api.github.com/.../assets/1)"), "", ""]

        def fake_run(command, **kwargs):
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch.object(MODULE, "run", side_effect=fake_run), patch.object(
            MODULE.time, "sleep"
        ) as sleep:
            result = MODULE.run_with_retry(["gh", "release", "download", "tag"])
        self.assertEqual(result, "")
        self.assertEqual(sleep.call_count, 1)
        sleep.assert_called_once_with(4.0)

    def test_backoff_grows_exponentially_across_attempts(self):
        outcomes = [
            failure(stderr="HTTP 502"),
            failure(stderr="HTTP 503"),
            failure(stderr="HTTP 500"),
            "",
        ]

        def fake_run(command, **kwargs):
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch.object(MODULE, "run", side_effect=fake_run), patch.object(
            MODULE.time, "sleep"
        ) as sleep:
            MODULE.run_with_retry(["gh", "release", "download", "tag"])
        self.assertEqual(
            [entry.args[0] for entry in sleep.call_args_list], [4.0, 8.0, 16.0]
        )

    def test_rate_limit_is_retried(self):
        outcomes = [failure(stderr="HTTP 403: API rate limit exceeded"), ""]

        def fake_run(command, **kwargs):
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch.object(MODULE, "run", side_effect=fake_run), patch.object(
            MODULE.time, "sleep"
        ) as sleep:
            MODULE.run_with_retry(["gh", "release", "download", "tag"])
        self.assertEqual(sleep.call_count, 1)

    def test_permission_failure_is_not_retried(self):
        with patch.object(
            MODULE, "run", side_effect=failure(stderr="HTTP 403: Resource not accessible")
        ), patch.object(MODULE.time, "sleep") as sleep:
            with self.assertRaises(subprocess.CalledProcessError):
                MODULE.run_with_retry(["gh", "release", "download", "tag"])
        sleep.assert_not_called()

    def test_not_found_is_not_retried(self):
        with patch.object(
            MODULE, "run", side_effect=failure(stderr="HTTP 404: Not Found")
        ), patch.object(MODULE.time, "sleep") as sleep:
            with self.assertRaises(subprocess.CalledProcessError):
                MODULE.run_with_retry(["gh", "release", "download", "tag"])
        sleep.assert_not_called()

    def test_retry_budget_is_bounded_and_reraises_the_last_failure(self):
        attempts = []

        def fake_run(command, **kwargs):
            attempts.append(command)
            raise failure(stderr="HTTP 500")

        with patch.object(MODULE, "run", side_effect=fake_run), patch.object(
            MODULE.time, "sleep"
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                MODULE.run_with_retry(["gh", "release", "download", "tag"], attempts=4)
        self.assertEqual(len(attempts), 4)

    def test_the_asset_audit_uses_the_retrying_download(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("run_with_retry(", source)
        # The retry helper must actually wrap the download, not just exist.
        self.assertRegex(
            source,
            r"for name in missing:\s*(?:#[^\n]*\n\s*)*run_with_retry\(",
        )


if __name__ == "__main__":
    unittest.main()