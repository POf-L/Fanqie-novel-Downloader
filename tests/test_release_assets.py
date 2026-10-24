"""Uploads go to the pre-created Draft by release ID, never by tag.

The 2026-10-22 unsigned release failed in finalize-unsigned-release because
linux-amd64.deb had no .sig: a parallel upload step missed the Draft created by
release-bootstrap, created a second same-tag Draft, and the assets were split
across the two.  These tests pin the fix: release-bootstrap resolves exactly one
Draft and hands its ID to every upload step, the uploader refuses to work
without that ID, and nothing in the build workflow can create a Draft by tag.
"""

import importlib.util
import io
import json
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


TAURI_ACTION_USES = "uses: tauri-apps/tauri-action@1deb371b0cd8bd54025b384f1cd735e725c4060f # v1.0.0"

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release-assets.py"
WORKFLOW = ROOT / ".github" / "workflows" / "build-release.yml"
MERGE_DRAFTS = ROOT / ".github" / "workflows" / "maintenance-merge-drafts.yml"
SPEC = importlib.util.spec_from_file_location("release_assets", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

REPO = "POf-L/Fanqie-novel-Downloader"
TAG = "unsigned-v2099.1.1-r1"


class FakeGitHub:
    """A tiny in-memory GitHub that records every gh invocation."""

    def __init__(self, releases, assets=None, failures=None):
        self.releases = releases
        self.assets = assets or {}
        self.failures = list(failures or [])
        self.calls = []
        self.next_asset_id = 1000

    def __call__(self, arguments, input_path=None):
        self.calls.append((list(arguments), input_path))
        if self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise subprocess.CalledProcessError(1, ["gh", *arguments], "", failure)
        assert arguments[0] == "api", arguments
        method = "GET"
        if "--method" in arguments:
            method = arguments[arguments.index("--method") + 1]
        endpoint = next(
            value for value in arguments[1:]
            if value.startswith("repos/") or value.startswith("https://")
        )
        match = re.fullmatch(
            rf"repos/{REPO}/releases\?per_page=(\d+)&page=(\d+)", endpoint
        )
        if match and method == "GET":
            size, page = int(match.group(1)), int(match.group(2))
            return json.dumps(self.releases[(page - 1) * size: page * size])
        match = re.fullmatch(rf"repos/{REPO}/releases/(\d+)", endpoint)
        if match and method == "GET":
            release_id = int(match.group(1))
            for release in self.releases:
                if release["id"] == release_id:
                    return json.dumps(release)
            raise subprocess.CalledProcessError(1, arguments, "", "HTTP 404")
        match = re.fullmatch(
            rf"repos/{REPO}/releases/(\d+)/assets\?per_page=(\d+)&page=(\d+)",
            endpoint,
        )
        if match and method == "GET":
            items = self.assets.setdefault(int(match.group(1)), [])
            size, page = int(match.group(2)), int(match.group(3))
            return json.dumps(items[(page - 1) * size: page * size])
        match = re.fullmatch(rf"repos/{REPO}/releases/assets/(\d+)", endpoint)
        if match and method == "DELETE":
            asset_id = int(match.group(1))
            for items in self.assets.values():
                items[:] = [item for item in items if item["id"] != asset_id]
            return ""
        match = re.fullmatch(
            rf"https://uploads\.github\.com/repos/{REPO}/releases/(\d+)/assets\?name=(.+)",
            endpoint,
        )
        if match and method == "POST":
            assert input_path is not None
            self.next_asset_id += 1
            asset = {"id": self.next_asset_id, "name": Path(input_path).name}
            self.assets.setdefault(int(match.group(1)), []).append(asset)
            return json.dumps(asset)
        raise AssertionError(f"unexpected gh call: {method} {endpoint}")


def client(fake):
    return MODULE.ReleaseClient(REPO, gh=fake, sleep=lambda _seconds: None)


def release(release_id, tag=TAG, draft=True):
    return {"id": release_id, "tag_name": tag, "draft": draft}


class ResolveTest(unittest.TestCase):
    def test_resolves_the_single_draft_for_the_tag(self):
        fake = FakeGitHub([release(7, "v1", draft=False), release(42)])
        self.assertEqual(client(fake).resolve(TAG, require_draft=True), 42)

    def test_duplicate_same_tag_releases_fail_instead_of_picking_one(self):
        fake = FakeGitHub([release(42), release(43)])
        with self.assertRaisesRegex(MODULE.ReleaseAssetError, "merge split unsigned drafts"):
            client(fake).resolve(TAG)

    def test_waits_for_an_eventually_consistent_release_list(self):
        fake = FakeGitHub([])
        lookups = []

        def sleep(_seconds):
            lookups.append(1)
            if len(lookups) == 2:
                fake.releases.append(release(42))

        resolver = MODULE.ReleaseClient(REPO, gh=fake, sleep=sleep)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(resolver.resolve(TAG), 42)

    def test_missing_release_fails(self):
        with self.assertRaisesRegex(MODULE.ReleaseAssetError, "no release found"), \
                redirect_stderr(io.StringIO()):
            client(FakeGitHub([])).resolve(TAG, lookups=2)

    def test_published_release_is_rejected_when_a_draft_is_required(self):
        with self.assertRaisesRegex(MODULE.ReleaseAssetError, "not a draft"):
            client(FakeGitHub([release(42, draft=False)])).resolve(TAG, require_draft=True)

    def test_pages_through_small_windows(self):
        releases = [release(index, f"v{index}", draft=False) for index in range(1, 61)]
        releases.append(release(99))
        fake = FakeGitHub(releases)
        self.assertEqual(client(fake).resolve(TAG), 99)
        self.assertTrue(all("per_page=30" in call[0][1] for call in fake.calls))

    def test_cli_writes_the_release_id_job_output(self):
        fake = FakeGitHub([release(42)])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            with redirect_stdout(io.StringIO()):
                code = MODULE.main(
                    ["resolve", "--repo", REPO, "--tag", TAG, "--require-draft",
                     "--github-output", str(output)],
                    client=client(fake),
                )
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "release_id=42\n")


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.deb = Path(self.tmp.name) / "FanqieNovelDownloader-tauri-linux-amd64.deb"
        self.deb.write_bytes(b"deb")
        self.sig = Path(self.tmp.name) / "FanqieNovelDownloader-tauri-linux-amd64.deb.sig"
        self.sig.write_bytes(b"sig")

    def run_cli(self, fake, *arguments):
        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            code = MODULE.main(list(arguments), client=client(fake))
        return code, stderr.getvalue()

    def test_uploads_by_release_id_and_replaces_same_name_assets(self):
        fake = FakeGitHub(
            [release(42)],
            assets={42: [{"id": 5, "name": self.deb.name}, {"id": 6, "name": "keep.txt"}]},
        )
        code, _ = self.run_cli(
            fake, "upload", "--repo", REPO, "--release-id", "42", "--tag", TAG,
            str(self.deb), str(self.sig),
        )
        self.assertEqual(code, 0)
        names = sorted(asset["name"] for asset in fake.assets[42])
        self.assertEqual(names, sorted(["keep.txt", self.deb.name, self.sig.name]))
        self.assertNotIn(5, [asset["id"] for asset in fake.assets[42]])
        posts = [call for call in fake.calls if "POST" in call[0]]
        self.assertEqual(len(posts), 2)
        for arguments, _input in posts:
            self.assertTrue(
                any("/releases/42/assets?name=" in value for value in arguments)
            )

    def test_missing_release_id_fails_without_touching_github(self):
        fake = FakeGitHub([release(42)])
        for value in ("", "  "):
            code, stderr = self.run_cli(
                fake, "upload", "--repo", REPO, "--release-id", value, "--tag", TAG,
                str(self.deb),
            )
            self.assertEqual(code, 1)
            self.assertIn("missing release ID", stderr)
        self.assertEqual(fake.calls, [])

    def test_release_id_carrying_another_tag_is_refused(self):
        fake = FakeGitHub([release(42, tag="unsigned-v2099.1.1-r2")])
        code, stderr = self.run_cli(
            fake, "upload", "--repo", REPO, "--release-id", "42", "--tag", TAG,
            str(self.deb),
        )
        self.assertEqual(code, 1)
        self.assertIn("refusing to touch another release", stderr)
        self.assertFalse(any("POST" in call[0] for call in fake.calls))

    def test_never_creates_or_looks_up_a_release_by_tag(self):
        fake = FakeGitHub([release(42)])
        self.run_cli(
            fake, "upload", "--repo", REPO, "--release-id", "42", "--tag", TAG,
            str(self.deb),
        )
        for arguments, _input in fake.calls:
            joined = " ".join(arguments)
            self.assertNotIn("releases/tags/", joined)
            self.assertNotIn("releases?", joined)
            if "POST" in arguments:
                self.assertIn("uploads.github.com", joined)

    def test_transient_upload_failure_is_retried_into_the_same_release(self):
        fake = FakeGitHub([release(42)])
        real = fake.__call__
        state = {"failed": False}

        def flaky(arguments, input_path=None):
            if "POST" in arguments and not state["failed"]:
                state["failed"] = True
                fake.calls.append((list(arguments), input_path))
                raise subprocess.CalledProcessError(1, arguments, "", "HTTP 502")
            return real(arguments, input_path)

        uploader = MODULE.ReleaseClient(REPO, gh=flaky, sleep=lambda _s: None)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            uploader.upload(42, TAG, [self.deb])
        self.assertEqual([asset["name"] for asset in fake.assets[42]], [self.deb.name])

    def test_delete_removes_only_named_assets_and_ignores_missing(self):
        fake = FakeGitHub(
            [release(42)],
            assets={42: [{"id": 5, "name": "old.AppImage"}, {"id": 6, "name": "keep.deb"}]},
        )
        code, _ = self.run_cli(
            fake, "delete", "--repo", REPO, "--release-id", "42", "--tag", TAG,
            "old.AppImage", "old.AppImage.sig",
        )
        self.assertEqual(code, 0)
        self.assertEqual([asset["name"] for asset in fake.assets[42]], ["keep.deb"])


class WorkflowUsesReleaseIdTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def job(self, name):
        section = self.workflow.split(f"\n  {name}:\n", 1)[1]
        return re.split(r"\n  [a-z][a-z0-9-]*:\n", section, maxsplit=1)[0]

    def test_bootstrap_publishes_the_resolved_draft_id(self):
        job = self.job("release-bootstrap")
        self.assertIn("release_id: ${{ steps.release-id.outputs.release_id }}", job)
        self.assertIn("id: release-id", job)
        self.assertIn("python scripts/release-assets.py resolve", job)
        self.assertIn("--require-draft", job)
        self.assertIn('--github-output "${GITHUB_OUTPUT}"', job)
        self.assertLess(job.index("- name: Create draft release"), job.index("id: release-id"))

    def test_tauri_action_never_gets_a_tag_in_release_jobs(self):
        for name in ("desktop", "desktop-fallback"):
            job = self.job(name)
            self.assertEqual(job.count(TAURI_ACTION_USES), 1)
            step = job.split(TAURI_ACTION_USES, 1)[1].split("\n      - name:", 1)[0]
            self.assertIn("needs.release-bootstrap.outputs.release_id || ''", step)
            self.assertIn("releaseId: ", step)
            for forbidden in ("tagName:", "releaseName:", "releaseDraft:", "prerelease:"):
                self.assertNotIn(forbidden, step)
        macos = self.job("macos-unsigned-build")
        self.assertIn('tagName: ""', macos)
        self.assertNotIn("releaseId:", macos)

    def test_no_upload_step_resolves_the_release_by_tag(self):
        self.assertNotIn("gh release upload", self.workflow)
        self.assertNotIn("delete-asset", self.workflow)
        self.assertNotIn('"release",\n                  "upload"', self.workflow)
        for name in ("desktop", "desktop-fallback", "android", "ios"):
            job = self.job(name)
            self.assertIn("path: release-wrapper", job)
            self.assertIn("- name: Require pre-created release ID", job)
            uploads = job.count("release-assets.py") + job.count("uploader,")
            self.assertGreaterEqual(uploads, 1, name)
            self.assertGreaterEqual(
                job.count("RELEASE_ID: ${{ needs.release-bootstrap.outputs.release_id }}"),
                2,
                name,
            )
        publish = self.job("macos-unsigned-publish")
        self.assertIn("release-wrapper/scripts/release-assets.py upload", publish)
        self.assertIn("RELEASE_ID: ${{ needs.macos-unsigned-bootstrap.outputs.release_id }}", publish)
        self.assertIn(
            "release_id: ${{ steps.release-id.outputs.release_id }}",
            self.job("macos-unsigned-bootstrap"),
        )

    def test_missing_release_id_stops_the_job_instead_of_creating_a_draft(self):
        guard = self.workflow.split("- name: Require pre-created release ID", 1)[1]
        guard = guard.split("\n      - name:", 1)[0]
        self.assertIn('[[ ! "${RELEASE_ID}" =~ ^[1-9][0-9]*$ ]]', guard)
        self.assertIn("exit 1", guard)
        self.assertEqual(
            self.workflow.count("- name: Require pre-created release ID"), 4
        )

    def test_fallback_checks_assets_of_the_pre_created_draft(self):
        job = self.job("desktop-fallback")
        check = job.split("- name: Check whether native build already uploaded assets", 1)[1]
        check = check.split("\n      - name:", 1)[0]
        self.assertIn("release-assets.py list", check)
        self.assertNotIn("gh release view", check)

    def test_finalizers_receive_the_release_id(self):
        for name, script in (
            ("finalize", "finalize-release.py"),
            ("finalize-unsigned-release", "finalize-unsigned-release.py"),
        ):
            job = self.job(name)
            self.assertIn('--release-id "${RELEASE_ID}"', job)
            self.assertIn(f"scripts/{script}", job)
            source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
            self.assertIn('"--release-id"', source)
            self.assertIn("resolve_database_id(repo, tag, args.release_id)", source)

    def test_merge_drafts_maintenance_stays_available_as_a_fallback(self):
        self.assertTrue(MERGE_DRAFTS.is_file())
        self.assertIn("workflow_dispatch:", MERGE_DRAFTS.read_text(encoding="utf-8"))


class FinalizerReleaseIdTest(unittest.TestCase):
    def load(self, name):
        spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / name)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_explicit_id_skips_the_tag_lookup(self):
        for name in ("finalize-release.py", "finalize-unsigned-release.py"):
            module = self.load(name)
            module.release_id = lambda *_args: self.fail("tag lookup used")
            self.assertEqual(module.resolve_database_id(REPO, TAG, "42"), 42)

    def test_without_id_the_old_tag_lookup_still_works(self):
        for name in ("finalize-release.py", "finalize-unsigned-release.py"):
            module = self.load(name)
            module.release_id = lambda _repo, _tag: 7
            self.assertEqual(module.resolve_database_id(REPO, TAG, ""), 7)

    def test_invalid_id_is_rejected(self):
        for name in ("finalize-release.py", "finalize-unsigned-release.py"):
            module = self.load(name)
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                module.resolve_database_id(REPO, TAG, "abc")


if __name__ == "__main__":
    unittest.main()
