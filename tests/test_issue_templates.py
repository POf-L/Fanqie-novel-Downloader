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

    def test_no_issue_form_or_doc_requires_a_star(self):
        for name, form in self.forms.items():
            with self.subTest(name=name):
                self.assertNotIn("Star", form)
        for doc in ("README.md", "CONTRIBUTING.md"):
            with self.subTest(doc=doc):
                text = (ROOT / doc).read_text(encoding="utf-8")
                self.assertNotIn("门禁", text)
                self.assertNotIn("公开 Star", text)
                self.assertNotIn("不需要 Star", text)

    def test_star_gate_workflow_is_removed(self):
        self.assertFalse((WORKFLOW_DIR / "issue-star-gate.yml").exists())
        for path in (ROOT / ".github").rglob("*"):
            if path.is_file():
                with self.subTest(path=str(path.relative_to(ROOT))):
                    text = path.read_text(encoding="utf-8")
                    self.assertNotIn("fanqie-star-gate", text)
                    self.assertNotIn("listReposStarredByUser", text)

    def test_feature_request_requires_reading_product_boundaries(self):
        feature = self.forms["feature-request.yml"]
        self.assertIn("CONTRIBUTING.md#产品边界", feature)
        self.assertRegex(
            feature,
            r"我读过 CONTRIBUTING 中的“产品边界”[^\n]*\n\s+required: true",
        )
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("## 产品边界", contributing)
        table_rows = re.findall(r"^\| (?!不做什么|---)[^|]+\| [^|]+\|$", contributing, re.MULTILINE)
        self.assertGreaterEqual(len(table_rows), 5)

    def test_bug_report_requires_latest_version_search_and_version_number(self):
        form = self.forms["bug-report.yml"]
        self.assertRegex(form, r"我已更新到 Releases 中的最新版本[^\n]*\n\s+required: true")
        self.assertRegex(form, r"我已搜索现有 Issue[^\n]*\n\s+required: true")
        version = form[form.index("id: version"):form.index("id: platform")]
        self.assertIn("required: true", version)

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
