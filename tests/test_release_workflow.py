import re
import unittest
from pathlib import Path


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

    def test_finalization_normalizes_and_rechecks_updater_metadata(self):
        self.assertIn("scripts/finalize-release.py", self.workflow)
        self.assertNotIn("releases/tags/${TAG_NAME}", self.workflow)
        self.assertIn("release_highlights:", self.workflow)
        self.assertIn("--highlights-file release-highlights.md", self.workflow)

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
