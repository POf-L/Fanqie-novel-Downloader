# 参与贡献

这个仓库负责 Issue 受理、发布说明和 GitHub Actions 发布调度。应用源码不在本仓库，
因此这里不接受修改应用行为的 Pull Request；应用相关的问题请通过 Issue 反馈。

## 提交 Issue

请选择对应的结构化表单，并填写发布版本、平台与架构、复现步骤及脱敏后的日志或截图。
提交 Issue 前需要先公开 Star 当前项目；首次核验未通过时，Actions 会礼貌提醒并保留
Issue 开放 10 分钟。宽限期内通过复查会删除提醒并继续开放，超时仍未通过才以
`not planned` 关闭。对于官方 API 的 JSON 错误，请保留 endpoint 路径、HTTP 状态码、
Content-Type 和简短响应预览；删除 query、签名、token、Cookie 和设备标识。

## 修改工作流、发布脚本与 Issue 表单

修改 `.github/workflows`、`.github/ISSUE_TEMPLATE` 或 `scripts/` 时，请同步增加或调整
自动化测试，并运行：

```powershell
python -m unittest discover -s tests -p 'test_*.py'
actionlint -no-color
git diff --check
```

不要提交发布凭据、更新签名私钥、下载产物或任何应用源码快照。`.gitignore` 已经覆盖
构建与校验用的临时目录，提交前请确认 `git status` 中不包含这些内容。

报告敏感问题前请先阅读 `SECURITY.md`，并使用私密漏洞报告入口。
