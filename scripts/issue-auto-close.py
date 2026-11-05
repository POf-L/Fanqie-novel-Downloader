#!/usr/bin/env python3
"""维护者回复后 24 小时没有回音的 Issue 自动关闭；作者再留言时自动重新打开。

规则（与 CONTRIBUTING.md 的“Issue 自动关闭”一节保持一致）：

关闭（sweep，定时每小时跑一次）需要同时满足：
- Issue 开着，不是仓库所有者或机器人提的，没有“保持开启”标签；
- 作者最后一次发言（提交、评论、自己编辑正文或评论）之后，至少有一条维护者的评论；
- 那之后的评论全部来自维护者或机器人（有其他人参与讨论时不关）；
- 最后一条评论（或最近一次重新打开，取较晚的）距今超过 24 小时。

关闭原因：
- 有“已修复待确认”标签 -> completed；
- 有“需要日志”标签，或维护者最后一条回复在等日志、等补充信息 -> not planned；
- 维护者最后一条回复附了发布链接（功能已实现、问题已修复）-> completed；
- 其余判断不了的 -> not planned。

重新打开（reopen，由 issue_comment 触发）：Issue 是被机器人关闭的，评论人是 Issue 作者。
维护者手动关闭的不会被重新打开。

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
NEEDS_LOG_LABEL = "需要日志"
FIXED_LABEL = "已修复待确认"
MARKER = "<!-- fanqie-auto-close -->"
REOPEN_MARKER = "<!-- fanqie-auto-reopen -->"
MAINTAINER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}

# 维护者在等对方补日志、补信息时的说法。
WAITING_PATTERN = re.compile(
    r"诊断日志|附上[^\n]{0,12}日志|补交|补充以下|麻烦补|先保持打开|收到[^\n]{0,20}后我再"
    r"|attach[^\n]{0,30}log|diagnostic log|please provide",
    re.IGNORECASE,
)
RELEASE_LINK = re.compile(r"/releases/tag/")

CLOSE_COMPLETED = (
    f"{MARKER}\n"
    "超过 24 小时没有收到回复，按规则自动关闭（已处理）。"
    "更新后还有问题，直接在这里留言就会自动重新打开。"
)
CLOSE_NOT_PLANNED = (
    f"{MARKER}\n"
    "超过 24 小时没有收到回复，已自动关闭。"
    "补充信息（例如诊断日志）后直接在这里留言，会自动重新打开。"
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


def close_reason(labels: set[str], last_maintainer_body: str) -> str:
    if FIXED_LABEL in labels:
        return "completed"
    if NEEDS_LOG_LABEL in labels or WAITING_PATTERN.search(last_maintainer_body):
        return "not_planned"
    if RELEASE_LINK.search(last_maintainer_body):
        return "completed"
    return "not_planned"


def decide(issue: dict, now: datetime, owner: str) -> Decision:
    """判断一条开着的 Issue 现在该不该自动关闭。issue 是 GraphQL 返回的节点。"""
    labels = {node["name"] for node in issue.get("labels", {}).get("nodes", [])}
    if EXEMPT_LABEL in labels:
        return Decision(False, f"有“{EXEMPT_LABEL}”标签")
    author = issue.get("author")
    author_login = login_of(author)
    if not author_login or is_bot(author) or author_login == owner:
        return Decision(False, "仓库所有者、机器人或已注销用户提的")
    if issue.get("authorAssociation") in MAINTAINER_ASSOCIATIONS:
        return Decision(False, "维护者自己提的")

    comments = issue.get("comments", {}).get("nodes", [])

    # 作者最后一次发言：提交、评论、自己编辑正文或评论。
    activity = [parse_time(issue["createdAt"])]
    if login_of(issue.get("editor")) == author_login:
        activity.append(parse_time(issue.get("lastEditedAt")))
    for c in comments:
        if login_of(c.get("author")) == author_login:
            activity.append(parse_time(c["createdAt"]))
            if login_of(c.get("editor")) == author_login:
                activity.append(parse_time(c.get("lastEditedAt")))
    last_author = max(t for t in activity if t)

    after = [c for c in comments if parse_time(c["createdAt"]) > last_author]
    if not after:
        return Decision(False, "最后发言的是作者，或者还没人回复")
    if any(not is_maintainer(c, owner) and not is_bot(c.get("author")) for c in after):
        return Decision(False, "作者之后有其他人参与讨论")
    maintainer_replies = [c for c in after if is_maintainer(c, owner)]
    if not maintainer_replies:
        return Decision(False, "维护者还没回复（只有机器人的自动说明）")

    since = parse_time(after[-1]["createdAt"])
    for node in issue.get("timelineItems", {}).get("nodes", []):
        reopened = parse_time((node or {}).get("createdAt"))
        if reopened and reopened > since:
            since = reopened
    if now - since < GRACE:
        return Decision(False, f"距离最后一条回复不到 24 小时（{since.isoformat()}）")

    reason = close_reason(labels, maintainer_replies[-1].get("body") or "")
    return Decision(True, f"维护者回复后超过 24 小时没有回音（{since.isoformat()}）", reason)


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
            body = CLOSE_COMPLETED if decision.state_reason == "completed" else CLOSE_NOT_PLANNED
            try:
                comment(repo, number, body)
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
