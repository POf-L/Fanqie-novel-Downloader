#!/usr/bin/env python3
"""按仓库结构化表单给新 Issue 分类，并用中文留一次初步回复。"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

MARKER = "<!-- fanqie-initial-triage -->"
OWNER = os.environ.get("GITHUB_REPOSITORY", "").split("/", 1)[0]
REPO = os.environ.get("GH_REPO", os.environ.get("GITHUB_REPOSITORY", ""))
ISSUE = os.environ.get("ISSUE", "")
AUTHOR = os.environ.get("AUTHOR", "")

CATEGORIES = {
    "错误反馈": re.compile(r"^\[bug\]", re.I),
    "增强功能": re.compile(r"^\[feature\]", re.I),
    "求助": re.compile(r"^\[help\]", re.I),
}
LOG_PATTERN = re.compile(
    r"github\.com/(?:user-attachments/files/\d+/|[^/\s]+/[^/\s]+/files/\d+/)[^\s)]+\.(?:log|txt|zip|7z|gz)"
    r"|event=(?:safe_log_started|startup_step)|fanqie-diagnostic-",
    re.I,
)

MESSAGES = {
    "错误反馈": "谢谢提交复现信息和诊断日志。我会按你填写的版本与平台先核对；如果还需要补充，会在这里具体说明。",
    "增强功能": "谢谢把使用场景和边界写得这么清楚。我已按“增强功能”归类，会结合现有功能评估；这条回复不代表已经排期或承诺版本。",
    "求助": "谢谢说明使用场景。我会先根据你提供的版本、平台和步骤看一下；如果还缺关键复现信息，会在这里具体问你。",
}


def gh(*args: str, stdin: str | None = None) -> str:
    result = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"gh {args[0]} 失败")
    return result.stdout


def comment_body(category: str) -> str:
    return f"{MARKER}\n{MESSAGES[category]}"


def category_for(title: str, labels: set[str]) -> str | None:
    for label, prefix in CATEGORIES.items():
        if label in labels or prefix.search(title.strip()):
            return label
    return None


def triage(repo: str, number: str, author: str) -> int:
    issue = json.loads(gh("api", f"repos/{repo}/issues/{number}"))
    if issue.get("pull_request") or not author or author == repo.split("/", 1)[0]:
        print("跳过仓库所有者或非 Issue")
        return 0
    labels = {label["name"] for label in issue.get("labels", [])}
    category = category_for(issue.get("title", ""), labels)
    if not category:
        print("标题和现有标签均无法归类，保留人工判断")
        return 0
    if category not in labels:
        gh("api", "-X", "POST", f"repos/{repo}/issues/{number}/labels", "--input", "-",
           stdin=json.dumps({"labels": [category]}, ensure_ascii=False))
        print(f"已添加分类标签：{category}")
    body = issue.get("body") or ""
    if category == "错误反馈" and not LOG_PATTERN.search(body):
        print("缺诊断日志，交由专门的日志检查流程回复")
        return 0
    comments = json.loads(gh("api", f"repos/{repo}/issues/{number}/comments"))
    if any(MARKER in (comment.get("body") or "") for comment in comments):
        print("初步回复已存在")
        return 0
    gh("api", "-X", "POST", f"repos/{repo}/issues/{number}/comments", "--input", "-",
       stdin=json.dumps({"body": comment_body(category)}, ensure_ascii=False))
    print(f"已按“{category}”回复")
    return 0


def main() -> int:
    if not REPO or not ISSUE or not AUTHOR:
        print("缺少 GH_REPO、ISSUE 或 AUTHOR", file=sys.stderr)
        return 2
    try:
        return triage(REPO, ISSUE, AUTHOR)
    except RuntimeError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
