#!/usr/bin/env python3
"""只关闭明确标记为“等待反馈”且作者 24 小时未回应的 Issue。

定时任务每 30 分钟检查一次。仅当 Issue 带“等待反馈”标签、维护者/自动检查
在作者最近发言之后已回复、且之后没有用户继续发言并满 24 小时才关闭；
“保持开启”、仓库所有者、机器人和维护者自己提交的 Issue 不自动关闭。
作者在自动关闭后再次评论会自动重新打开。

正文和评论只通过 GitHub API 读取，不会拼进命令行。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

GRACE = timedelta(hours=24)
EXEMPT_LABEL = "保持开启"
WAITING_LABEL = "等待反馈"
MARKER = "<!-- fanqie-auto-close -->"
REOPEN_MARKER = "<!-- fanqie-auto-reopen -->"
MAINTAINER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}

CLOSE_WAITING = (
    f"{MARKER}\n"
    "超过 24 小时没有收到回复，已自动关闭。如仍有问题可重新打开。"
)
REOPEN_BODY = f"{REOPEN_MARKER}\n收到回复，已自动重新打开，维护者会继续跟进。"


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def login_of(actor: dict | None) -> str:
    return (actor or {}).get("login") or ""


def is_bot(actor: dict | None) -> bool:
    if not actor:
        return False
    login = login_of(actor)
    return actor.get("__typename") == "Bot" or login.endswith("[bot]") or login == "github-actions"


def is_maintainer(comment: dict, owner: str) -> bool:
    author = comment.get("author")
    if not author or is_bot(author):
        return False
    return login_of(author) == owner or comment.get("authorAssociation") in MAINTAINER_ASSOCIATIONS


class Decision(NamedTuple):
    close: bool
    why: str
    state_reason: str = ""


def decide(issue: dict, now: datetime, owner: str) -> Decision:
    """判断一条开着的 Issue 现在该不该自动关闭。issue 是 GraphQL 返回的节点。"""
    labels = {node["name"] for node in issue.get("labels", {}).get("nodes", [])}
    if WAITING_LABEL not in labels:
        return Decision(False, f"没有“{WAITING_LABEL}”标签")
    if EXEMPT_LABEL in labels:
        return Decision(False, f"有“{EXEMPT_LABEL}”标签")
    author = issue.get("author")
    author_login = login_of(author)
    if not author_login or is_bot(author) or author_login == owner:
        return Decision(False, "仓库所有者、机器人或已注销用户提的")
    if issue.get("authorAssociation") in MAINTAINER_ASSOCIATIONS:
        return Decision(False, "维护者自己提的")

    comments = issue.get("comments", {}).get("nodes", [])
    author_activity = [parse_time(issue.get("createdAt"))]
    if login_of(issue.get("editor")) == author_login:
        author_activity.append(parse_time(issue.get("lastEditedAt")))
    for comment in comments:
        if login_of(comment.get("author")) == author_login:
            author_activity.append(parse_time(comment.get("createdAt")))
            if login_of(comment.get("editor")) == author_login:
                author_activity.append(parse_time(comment.get("lastEditedAt")))
    author_times = [value for value in author_activity if value is not None]
    last_author = max(author_times) if author_times else None

    # 由“等待反馈”标签明确限定自动关闭范围。最近一次维护者/自动回复
    # 必须晚于作者的最新发言，且其后没有其他非维护者参与讨论。
    staff_comments = [
        comment for comment in comments
        if is_maintainer(comment, owner) or is_bot(comment.get("author"))
    ]
    if not staff_comments:
        return Decision(False, "还没有维护者回复")
    latest_staff = max(staff_comments, key=lambda item: parse_time(item["createdAt"]))
    since = parse_time(latest_staff.get("createdAt"))
    if since is None or (last_author is not None and last_author >= since):
        return Decision(False, "作者在最近一次等待反馈后仍有发言")
    after = [comment for comment in comments if parse_time(comment["createdAt"]) > since]
    if any(not is_maintainer(comment, owner) and not is_bot(comment.get("author")) for comment in after):
        return Decision(False, "等待反馈后有其他人参与讨论")

    for node in issue.get("timelineItems", {}).get("nodes", []):
        reopened = parse_time((node or {}).get("createdAt"))
        if reopened and reopened >= since:
            return Decision(False, "Issue 在最近回复后重新打开，需要重新等待维护者回复")
    if now - since < GRACE:
        return Decision(False, f"距离等待反馈回复不到 24 小时（{since.isoformat()}）")
    return Decision(True, f"“{WAITING_LABEL}”后超过 24 小时没有作者回复（{since.isoformat()}）", "not_planned")


def should_reopen(issue: dict, commenter: str) -> bool:
    """被机器人关闭、作者又留言的 Issue 才重新打开。"""
    if issue.get("state") != "CLOSED":
        return False
    author_login = login_of(issue.get("author"))
    if not author_login or commenter != author_login:
        return False
    closed = [n for n in issue.get("timelineItems", {}).get("nodes", []) if n]
    if not closed:
        return False
    return is_bot(closed[-1].get("actor"))


# ---------- GitHub API ----------

ISSUE_FIELDS = """
  number state createdAt lastEditedAt authorAssociation
  author { login __typename }
  editor { login }
  labels(first: 50) { nodes { name } }
  comments(last: 100) {
    nodes { createdAt lastEditedAt authorAssociation body author { login __typename } editor { login } }
  }
"""

SWEEP_QUERY = (
    """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: 30, after: $after, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {"""
    + ISSUE_FIELDS
    + """
        timelineItems(itemTypes: [REOPENED_EVENT], last: 1) { nodes { ... on ReopenedEvent { createdAt } } }
      }
    }
  }
}
"""
)

REOPEN_QUERY = (
    """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {"""
    + ISSUE_FIELDS
    + """
      timelineItems(itemTypes: [CLOSED_EVENT], last: 1) {
        nodes { ... on ClosedEvent { createdAt actor { login __typename } } }
      }
    }
  }
}
"""
)


def gh(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} 失败：{result.stderr.strip()}")
    return result.stdout


def graphql(query: str, **variables) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is None:
            continue
        flag = "-F" if isinstance(value, int) else "-f"
        args += [flag, f"{key}={value}"]
    return json.loads(gh(*args))["data"]


def split_repo(repo: str) -> tuple[str, str]:
    owner, name = repo.split("/", 1)
    return owner, name


def comment(repo: str, number: int, body: str) -> None:
    gh("api", "-X", "POST", f"repos/{repo}/issues/{number}/comments", "--input", "-",
       stdin=json.dumps({"body": body}))


def set_state(repo: str, number: int, state: str, state_reason: str) -> None:
    gh("api", "-X", "PATCH", f"repos/{repo}/issues/{number}", "--input", "-",
       stdin=json.dumps({"state": state, "state_reason": state_reason}))


def sweep(repo: str, dry_run: bool, now: datetime) -> int:
    owner, name = split_repo(repo)
    failures = 0
    after = None
    while True:
        page = graphql(SWEEP_QUERY, owner=owner, name=name, after=after)["repository"]["issues"]
        for issue in page["nodes"]:
            number = issue["number"]
            decision = decide(issue, now, owner)
            if not decision.close:
                print(f"#{number} 保留：{decision.why}")
                continue
            print(f"#{number} 关闭（{decision.state_reason}）：{decision.why}")
            if dry_run:
                continue
            try:
                comment(repo, number, CLOSE_WAITING)
                set_state(repo, number, "closed", decision.state_reason)
            except RuntimeError as error:
                failures += 1
                print(f"::error::#{number} 关闭失败：{error}")
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return 1 if failures else 0


def reopen(repo: str, number: int, commenter: str, dry_run: bool) -> int:
    owner, name = split_repo(repo)
    issue = graphql(REOPEN_QUERY, owner=owner, name=name, number=number)["repository"]["issue"]
    if not issue or not should_reopen(issue, commenter):
        print(f"#{number} 不需要重新打开")
        return 0
    print(f"#{number} 作者 {commenter} 在自动关闭后留言，重新打开")
    if not dry_run:
        set_state(repo, number, "open", "reopened")
        comment(repo, number, REOPEN_BODY)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", ""))
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sweep")
    reopen_parser = sub.add_parser("reopen")
    reopen_parser.add_argument("--issue", type=int, required=True)
    reopen_parser.add_argument("--commenter", required=True)
    args = parser.parse_args(argv)
    if "/" not in args.repo:
        parser.error("需要 --repo owner/name 或 GH_REPO")
    if args.command == "sweep":
        return sweep(args.repo, args.dry_run, datetime.now(timezone.utc))
    return reopen(args.repo, args.issue, args.commenter, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
