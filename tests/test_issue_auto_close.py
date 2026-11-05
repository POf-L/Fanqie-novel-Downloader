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

    def test_new_issue_without_replies_stays_open(self):
        result = self.decide(issue([]))
        self.assertFalse(result.close)

    def test_new_bug_with_only_log_check_bot_comment_stays_open(self):
        data = issue([c(BOT, "2026-11-04T08:00:10Z", "<!-- fanqie-log-check -->")], labels=["错误反馈", "需要日志"])
        result = self.decide(data)
        self.assertFalse(result.close)
        self.assertIn("维护者还没回复", result.why)

    def test_maintainer_reply_older_than_24h_closes(self):
        data = issue([c(MAINTAINER, "2026-11-04T18:51:44Z", f"已在 [2026.11.4-1822]({RELEASE}) 加了一个开关。")])
        result = self.decide(data)
        self.assertTrue(result.close)
        self.assertEqual(result.state_reason, "completed")

    def test_maintainer_reply_within_24h_stays_open(self):
        data = issue([c(MAINTAINER, "2026-11-06T00:00:00Z")])
        self.assertFalse(self.decide(data).close)

    def test_exactly_24h_boundary(self):
        data = issue([c(MAINTAINER, "2026-11-05T12:00:01Z")])
        self.assertFalse(self.decide(data).close)
        data = issue([c(MAINTAINER, "2026-11-05T12:00:00Z")])
        self.assertTrue(self.decide(data).close)

    def test_author_replied_after_maintainer_stays_open(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z"), c(USER, "2026-11-04T11:00:00Z")])
        result = self.decide(data)
        self.assertFalse(result.close)

    def test_author_edit_after_maintainer_counts_as_reply(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], edited_at="2026-11-06T00:00:00Z", editor=USER)
        self.assertFalse(self.decide(data).close)
        # 维护者自己改正文不算作者回应。
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], edited_at="2026-11-06T00:00:00Z", editor=MAINTAINER)
        self.assertTrue(self.decide(data).close)

    def test_author_comment_edit_after_maintainer_counts_as_reply(self):
        data = issue([
            c(USER, "2026-11-04T09:00:00Z", edited_at="2026-11-06T00:00:00Z", editor=USER),
            c(MAINTAINER, "2026-11-04T10:00:00Z"),
        ])
        self.assertFalse(self.decide(data).close)

    def test_bot_comment_after_maintainer_still_closes_and_clock_starts_from_last(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z"), c(BOT, "2026-11-05T20:00:00Z")])
        self.assertFalse(self.decide(data).close)
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z"), c(BOT, "2026-11-05T10:00:00Z")])
        self.assertTrue(self.decide(data).close)

    def test_third_party_comment_last_stays_open(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z"), c(OTHER, "2026-11-04T12:00:00Z")])
        result = self.decide(data)
        self.assertFalse(result.close)
        self.assertIn("其他人", result.why)

    def test_collaborator_counts_as_maintainer(self):
        helper = {"login": "helper", "__typename": "User"}
        data = issue([c(helper, "2026-11-04T10:00:00Z", association="COLLABORATOR")])
        self.assertTrue(self.decide(data).close)

    def test_exempt_label_stays_open(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], labels=["保持开启"])
        result = self.decide(data)
        self.assertFalse(result.close)
        self.assertIn("保持开启", result.why)

    def test_owner_bot_and_ghost_issues_are_skipped(self):
        for author in (MAINTAINER, BOT, None):
            with self.subTest(author=author):
                data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], author=author)
                self.assertFalse(self.decide(data).close)

    def test_recent_reopen_restarts_the_clock(self):
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], reopened="2026-11-06T01:00:00Z")
        self.assertFalse(self.decide(data).close)
        data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z")], reopened="2026-11-05T01:00:00Z")
        self.assertTrue(self.decide(data).close)

    def test_close_reasons(self):
        cases = [
            (["需要日志"], f"已在 {RELEASE} 加上开关。", "not_planned"),
            ([], f"在 {RELEASE} 做了改动……然后反馈结果，并**附上诊断日志文件**。", "not_planned"),
            ([], "需要你帮忙确认几件事……这个 issue 先保持打开。", "not_planned"),
            ([], f"已在 [2026.11.4-1127]({RELEASE}) 修复。更新后还有问题的话，麻烦说一下。", "completed"),
            (["已修复待确认"], "请更新后确认。", "completed"),
            ([], "这个需求我想一下。", "not_planned"),
            ([], f"Fixed in [2026.11.3-1650]({RELEASE}). If it still fails, please attach the log file.", "not_planned"),
        ]
        for labels, body, expected in cases:
            with self.subTest(body=body[:20], labels=labels):
                data = issue([c(MAINTAINER, "2026-11-04T10:00:00Z", body)], labels=labels)
                result = self.decide(data)
                self.assertTrue(result.close)
                self.assertEqual(result.state_reason, expected)

    def test_reason_uses_latest_maintainer_reply(self):
        data = issue([
            c(MAINTAINER, "2026-11-04T09:00:00Z", "麻烦补一下诊断日志。"),
            c(MAINTAINER, "2026-11-04T10:00:00Z", f"已在 {RELEASE} 修复。"),
        ])
        self.assertEqual(self.decide(data).state_reason, "completed")


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

    def test_runs_hourly_and_reopens_on_comment(self):
        self.assertRegex(self.wf, r'cron: "\d+ \* \* \* \*"')
        self.assertIn("issue_comment:", self.wf)
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

    def test_docs_and_templates_mention_the_rule(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("## Issue 自动关闭", contributing)
        self.assertIn("保持开启", contributing)
        self.assertIn("issue-auto-close.yml", contributing)
        for name in ("bug-report.yml", "feature-request.yml", "help-request.yml"):
            with self.subTest(name=name):
                form = (ROOT / ".github" / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8")
                self.assertIn("超过 24 小时没有回音的 Issue 会自动关闭", form)


if __name__ == "__main__":
    unittest.main()
