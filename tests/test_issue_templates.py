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
        cls.star_workflow = (WORKFLOW_DIR / "issue-star-gate.yml").read_text(
            encoding="utf-8"
        )

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

    def test_only_feature_requests_require_a_public_star(self):
        feature = self.forms["feature-request.yml"]
        self.assertIn("提交 Issue 前请先公开 Star 当前项目", feature)
        self.assertRegex(
            feature,
            r"我已公开 Star 当前项目[^\n]*10 分钟[^\n]*\n\s+required: true",
        )
        for name in ("bug-report.yml", "help-request.yml"):
            with self.subTest(name=name):
                self.assertNotIn("Star", self.forms[name])

        github_config = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / ".github").rglob("*")
            if path.is_file()
        )
        self.assertNotIn("是否 Star **不影响** Issue 的受理和处理", github_config)

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

    def test_star_gate_only_applies_to_feature_requests(self):
        workflow = self.star_workflow
        self.assertIn("function isFeatureRequest(issue)", workflow)
        self.assertIn("const featureLabel = '增强功能';", workflow)
        self.assertIn("const featureTitlePrefix = '[feature]';", workflow)
        enforce = workflow[workflow.index("async function enforce(issue)"):]
        self.assertLess(
            enforce.index("if (!isFeatureRequest(issue))"),
            enforce.index("hasVerifiableStar(author, issue.number)"),
        )
        self.assertIn("!item.pull_request && isFeatureRequest(item)", workflow)
        # 表单自动打的标签必须和门禁识别的标签一致。
        self.assertIn('labels: ["增强功能"]', self.forms["feature-request.yml"])
        self.assertIn('title: "[Feature] "', self.forms["feature-request.yml"])

    def test_star_gate_feature_detection_behaves(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if node is None:
            self.skipTest("node 不可用")
        workflow = self.star_workflow
        start = workflow.index("            const featureLabel")
        end = workflow.index("            async function enforce(issue)")
        snippet = "\n".join(line[12:] for line in workflow[start:end].splitlines())
        cases = [
            ({"labels": [{"name": "增强功能"}], "title": "x"}, True),
            ({"labels": ["增强功能"], "title": "x"}, True),
            ({"labels": [], "title": "  [Feature] 新功能"}, True),
            ({"labels": [{"name": "错误反馈"}], "title": "[Bug] 崩溃"}, False),
            ({"labels": [{"name": "求助"}], "title": "[Help] 怎么用"}, False),
            ({"title": None}, False),
        ]
        import json
        script = snippet + "\nconst cases = " + json.dumps(cases, ensure_ascii=False) + ";\n" + (
            "for (const [issue, want] of cases) {"
            " if (isFeatureRequest(issue) !== want) { console.error(JSON.stringify(issue)); process.exit(1); } }"
        )
        result = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_star_gate_checks_new_reopened_and_existing_issues(self):
        workflow = self.star_workflow
        self.assertIn("types: [opened, reopened]", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertIn('paths:\n      - ".github/workflows/issue-star-gate.yml"', workflow)
        self.assertIn("github.rest.issues.listForRepo", workflow)
        self.assertIn("state: 'open'", workflow)
        self.assertIn("!item.pull_request", workflow)

    def test_star_gate_uses_public_user_stars_and_default_token(self):
        workflow = self.star_workflow
        self.assertIn("github.rest.activity.listReposStarredByUser", workflow)
        self.assertNotIn("listStargazersForRepo", workflow)
        self.assertIn("github-token: ${{ secrets.GITHUB_TOKEN }}", workflow)
        self.assertNotIn("PRIVATE_SOURCE_TOKEN", workflow)
        self.assertNotIn("STAR_GATE_TOKEN", workflow)
        self.assertIn("permissions:\n  contents: read\n  issues: write", workflow)

    def test_star_gate_warns_waits_rechecks_and_only_then_closes(self):
        workflow = self.star_workflow
        self.assertIn("fanqie-star-gate:v2", workflow)
        self.assertIn("fanqie-star-gate:v1", workflow)
        self.assertIn("const gracePeriodMs = 10 * 60 * 1000", workflow)
        self.assertIn("ensureCurrentGateComment", workflow)
        self.assertIn("context.payload.action === 'reopened'", workflow)
        self.assertIn("status === 404 || status === 451", workflow)
        self.assertIn("感谢你花时间提交功能建议", workflow)
        self.assertIn("本 Issue 目前会保持开放", workflow)
        self.assertIn("await new Promise((resolve) => setTimeout(resolve, waitMs))", workflow)
        self.assertGreaterEqual(workflow.count("hasVerifiableStar(author, issue.number)"), 2)
        self.assertLess(
            workflow.index("ensureCurrentGateComment(issue, forceNewReminder)"),
            workflow.index("state: 'closed'"),
        )
        self.assertIn("state: 'closed'", workflow)
        self.assertIn("state_reason: 'not_planned'", workflow)

    def test_star_gate_deletes_its_reminder_when_the_author_stars(self):
        workflow = self.star_workflow
        self.assertIn("deleteGateComments", workflow)
        self.assertIn("github.rest.issues.deleteComment", workflow)
        self.assertIn("已在宽限期内公开 Star", workflow)
        self.assertIn("保持开放", workflow)
        self.assertNotIn("重新打开本 Issue", workflow)

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
