# Issue 提交入口

`.github/ISSUE_TEMPLATE` 提供三类结构化表单：

- `bug-report.yml`：可复现的软件故障、崩溃和异常行为。
- `feature-request.yml`：基于明确使用场景的功能建议。
- `help-request.yml`：安装、配置、使用方法及尚未确认的故障排查。

`config.yml` 关闭空白 Issue，并提供下载说明、Releases 和私密安全报告入口。错误反馈会收集
完整版本、平台、系统与架构、实际现象、复现步骤和预期结果；日志不是强制项，但公开内容必须
删除 token、签名、Cookie、设备标识和个人数据。表单使用仓库已有的 `错误反馈`、`增强功能`
和 `求助` 标签，不依赖额外的自动分类 Action。

Issue 的受理和处理与作者是否 Star 无关。仓库不查询 stargazer 列表、不要求公开 Star，
也不会因为未 Star 自动留言或关闭 Issue。这样既减少每次提交产生的 Actions 运行，也避免
把问题支持变成交换 Star 的条件。

`tests/test_issue_templates.py` 固定表单集合、必需字段、标签和上述自愿原则，并确保旧的
Star 核验工作流不会被重新引入。
