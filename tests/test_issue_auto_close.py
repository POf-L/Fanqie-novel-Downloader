import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "issue-auto-close.py"
SPEC = importlib.util.spec_from_file_location("issue_auto_close", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

OWNER = "POf-L"
USER = {"login": "reader", "__typename": "User"}
MAINTAINER = {"login": OWNER, "__typename": "User"}
BOT = {"login": "github-actions", "__typename": "Bot"}
OTHER = {"login": "someone", "__typename": "User"}
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
RELEASE = "https://github.com/POf-L/Fanqie-novel-Downloader/releases/tag/unsigned-v2026.11.4-1822-r790"


def c(author, at, body="感谢反馈。", association=None, edited_at=None, editor=None):
    if association is None:
        association = "OWNER" if author is MAINTAINER else "NONE"
    return {
        "author": author,
        "createdAt": at,
        "authorAssociation": association,
        "body": body,
        "lastEditedAt": edited_at,
        "editor": editor,
    }


def issue(comments, labels=(), author=USER, created="2026-11-04T08:00:00Z", reopened=None,
          edited_at=None, editor=None, association="NONE"):
    return {
        "number": 1,
        "state": "OPEN",
        "createdAt": created,
        "lastEditedAt": edited_at,
        "editor": editor,
        "authorAssociation": association,
        "author": author,
        "labels": {"nodes": [{"name": name} for name in labels]},
        "comments": {"nodes": list(comments)},
        "timelineItems": {"nodes": [{"createdAt": reopened}] if reopened else []},
    }


class DecideTest(unittest.TestCase):
    def decide(self, data, now=NOW):
        return MODULE.decide(data, now, OWNER)

    def test_requires_explicit_waiting_feedback_label(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")])
        self.assertFalse(self.decide(data).close)
        self.assertIn("等待反馈", self.decide(data).why)

    def test_waiting_more_than_24h_closes(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], labels=["等待反馈"])
        result = self.decide(data)
        self.assertTrue(result.close)
        self.assertEqual(result.state_reason, "not_planned")
        self.assertIn("24 小时", MODULE.CLOSE_WAITING)
        self.assertIn("如仍有问题可重新打开", MODULE.CLOSE_WAITING)

    def test_recent_waiting_reply_stays_open(self):
        data = issue([c(MAINTAINER, "2026-11-06T00:00:00Z")], labels=["等待反馈"])
        self.assertFalse(self.decide(data).close)

    def test_author_replied_after_maintainer_stays_open(self):
        data = issue([
            c(MAINTAINER, "2026-11-04T10:00:00Z"),
            c(USER, "2026-11-05T00:00:00Z"),
        ], labels=["等待反馈"])
        self.assertFalse(self.decide(data).close)

    def test_author_edit_after_maintainer_counts_as_reply(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], labels=["等待反馈"],
                     edited_at="2026-11-06T00:00:00Z", editor=USER)
        self.assertFalse(self.decide(data).close)

    def test_maintainer_edit_does_not_restart_the_author_clock(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], labels=["等待反馈"],
                     edited_at="2026-11-06T00:00:00Z", editor=MAINTAINER)
        self.assertTrue(self.decide(data).close)

    def test_third_party_comment_after_waiting_stays_open(self):
        data = issue([
            c(MAINTAINER, "2026-11-04T10:00:00Z"),
            c(OTHER, "2026-11-04T12:00:00Z"),
        ], labels=["等待反馈"])
        self.assertFalse(self.decide(data).close)

    def test_exempt_label_and_owner_bot_issues_stay_open(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], labels=["等待反馈", "保持开启"])
        self.assertFalse(self.decide(data).close)
        for author in (MAINTAINER, BOT, None):
            with self.subTest(author=author):
                data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")],
                             labels=["等待反馈"], author=author)
                self.assertFalse(self.decide(data).close)

    def test_reopened_issue_needs_a_fresh_maintainer_reply(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], labels=["等待反馈"],
                     reopened="2026-11-06T01:00:00Z")
        self.assertFalse(self.decide(data).close)


class ReopenTest(unittest.TestCase):
    def closed(self, actor):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")])
        data["state"] = "CLOSED"
        data["timelineItems"] = {"nodes": [{"createdAt": "2026-11-05T11:17:00Z", "actor": actor}]}
        return data

    def test_author_comment_reopens_bot_closed_issue(self):
        self.assertTrue(MODULE.should_reopen(self.closed(BOT), "reader"))

    def test_maintainer_closed_issue_is_not_reopened(self):
        self.assertFalse(MODULE.should_reopen(self.closed(MAINTAINER), "reader"))

    def test_other_commenter_does_not_reopen(self):
        self.assertFalse(MODULE.should_reopen(self.closed(BOT), "someone"))

    def test_open_issue_is_left_alone(self):
        data = self.closed(BOT)
        data["state"] = "OPEN"
        self.assertFalse(MODULE.should_reopen(data, "reader"))


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf = (ROOT / ".github" / "workflows" / "issue-auto-close.yml").read_text(encoding="utf-8")
        cls.log_check = (ROOT / ".github" / "workflows" / "issue-log-check.yml").read_text(encoding="utf-8")
        cls.triage_wf = (ROOT / ".github" / "workflows" / "issue-triage.yml").read_text(encoding="utf-8")

    def test_runs_every_30_minutes_and_reopens_on_comment(self):
        self.assertIn('cron: "*/30 * * * *"', self.wf)
        self.assertIn("issue_comment:", self.wf)
        self.assertIn("types: [opened]", self.triage_wf)
        self.assertIn("github.event.comment.user.login == github.event.issue.user.login", self.wf)
        self.assertIn("dry_run", self.wf)

    def test_only_closes_never_deletes_or_locks(self):
        self.assertIn("permissions: {}", self.wf)
        self.assertNotIn("contents: write", self.wf)
        script = SCRIPT.read_text(encoding="utf-8")
        for verb in ("deleteIssue", "issue delete", "/lock", "issue lock"):
            with self.subTest(verb=verb):
                self.assertNotIn(verb, self.wf)
                self.assertNotIn(verb, script)

    def test_user_content_is_not_interpolated_into_scripts(self):
        for block in self.wf.split("run: |")[1:]:
            self.assertNotIn("${{", block.split("\n  reopen:")[0])

    def test_log_check_can_remove_label_after_auto_close(self):
        self.assertIn("(github.event.issue.state == 'open' || github.event_name == 'issue_comment')", self.log_check)
        self.assertIn("等待反馈", self.log_check)
        self.assertIn("新 Issue 初步分流", self.triage_wf)
        self.assertIn("scripts/issue-triage.py", self.triage_wf)

    def test_docs_and_templates_mention_the_rule(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("## Issue 自动关闭", contributing)
        self.assertIn("等待反馈", contributing)
        self.assertIn("保持开启", contributing)
        self.assertIn("issue-auto-close.yml", contributing)
        for name in ("bug-report.yml", "feature-request.yml", "help-request.yml"):
            with self.subTest(name=name):
                form = (ROOT / ".github" / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8")
                self.assertIn("24 小时没有作者回复的 Issue 会自动关闭", form)


if __name__ == "__main__":
    unittest.main()
