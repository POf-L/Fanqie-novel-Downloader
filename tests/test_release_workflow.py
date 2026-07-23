import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-release.yml"
REPAIR_WORKFLOW = ROOT / ".github" / "workflows" / "repair-updater-metadata.yml"


class ReleaseWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.repair_workflow = REPAIR_WORKFLOW.read_text(encoding="utf-8")

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
        self.assertIn("scripts/normalize-updater-metadata.py", self.workflow)
        self.assertIn("--check", self.workflow)
        self.assertIn("gh release upload \"${TAG_NAME}\" release-check/latest.json", self.workflow)

    def test_repair_workflow_reuses_normalizer_and_updates_checksums(self):
        self.assertIn("name: Repair Updater Metadata", self.repair_workflow)
        self.assertIn("permissions:\n  contents: write", self.repair_workflow)
        self.assertIn("scripts/normalize-updater-metadata.py", self.repair_workflow)
        self.assertIn("--check", self.repair_workflow)
        self.assertIn("SHA256SUMS-release.txt", self.repair_workflow)
        self.assertIn('gh release upload "${tag}"', self.repair_workflow)


if __name__ == "__main__":
    unittest.main()
