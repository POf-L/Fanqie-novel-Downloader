import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
WORKFLOW_DIR = ROOT / ".github" / "workflows"


class IssueTemplateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = (TEMPLATE_DIR / "config.yml").read_text(encoding="utf-8")
        cls.forms = {
            path.name: path.read_text(encoding="utf-8")
            for path in TEMPLATE_DIR.glob("*.yml")
            if path.name != "config.yml"
        }

    def test_only_structured_issue_forms_are_enabled(self):
        self.assertIn("blank_issues_enabled: false", self.config)
        self.assertEqual(
            set(self.forms),
            {"bug-report.yml", "feature-request.yml", "help-request.yml"},
        )

    def test_forms_have_clear_titles_and_existing_labels(self):
        expected = {
            "bug-report.yml": ("错误反馈", 'title: "[Bug] "', "错误反馈"),
            "feature-request.yml": ("功能建议", 'title: "[Feature] "', "增强功能"),
            "help-request.yml": ("使用求助", 'title: "[Help] "', "求助"),
        }
        for name, (display_name, title, label) in expected.items():
            with self.subTest(name=name):
                form = self.forms[name]
                self.assertIn(f"name: {display_name}", form)
                self.assertIn(title, form)
                self.assertIn(f'labels: ["{label}"]', form)

    def test_forms_explain_that_stars_are_optional(self):
        for name, form in self.forms.items():
            with self.subTest(name=name):
                self.assertIn("是否 Star **不影响** Issue 的受理和处理", form)

        github_config = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / ".github").rglob("*")
            if path.is_file()
        )
        self.assertNotIn("listStargazersForRepo", github_config)
        self.assertFalse((WORKFLOW_DIR / "issue-star-gate.yml").exists())

    def test_form_field_ids_are_unique_and_well_formed(self):
        for name, form in self.forms.items():
            with self.subTest(name=name):
                ids = re.findall(r"^    id: ([a-z][a-z0-9_-]*)$", form, re.MULTILINE)
                self.assertTrue(ids)
                self.assertEqual(len(ids), len(set(ids)))

    def test_bug_report_collects_reproduction_context(self):
        form = self.forms["bug-report.yml"]
        for field in (
            "id: version",
            "id: platform",
            "id: environment",
            "id: problem",
            "id: reproduction",
            "id: expected",
            "id: logs",
        ):
            self.assertIn(field, form)

    def test_public_reports_warn_against_sensitive_data(self):
        for name in ("bug-report.yml", "help-request.yml"):
            with self.subTest(name=name):
                form = self.forms[name]
                self.assertIn("token", form)
                self.assertIn("设备标识", form)


if __name__ == "__main__":
    unittest.main()
