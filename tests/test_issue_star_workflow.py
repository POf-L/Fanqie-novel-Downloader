import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "issue-star-gate.yml"


class IssueStarWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_checks_new_issues(self):
        self.assertIn("issues:", self.workflow)
        self.assertIn("types: [opened]", self.workflow)

    def test_workflow_has_only_required_repository_permissions(self):
        self.assertIn("permissions:\n  contents: read\n  issues: write", self.workflow)
        self.assertNotIn("contents: write", self.workflow)

    def test_uses_paginated_stargazers_and_case_insensitive_login_match(self):
        self.assertIn("github.paginate.iterator", self.workflow)
        self.assertIn("github.rest.activity.listStargazersForRepo", self.workflow)
        self.assertIn("author.toLowerCase()", self.workflow)
        self.assertIn("stargazer.login.toLowerCase()", self.workflow)

    def test_unstarred_issue_is_explained_and_closed(self):
        self.assertIn("github.rest.issues.createComment", self.workflow)
        self.assertIn('state: "closed"', self.workflow)
        self.assertIn('state_reason: "not_planned"', self.workflow)
        self.assertIn("重新提交一个新的 Issue", self.workflow)


if __name__ == "__main__":
    unittest.main()
