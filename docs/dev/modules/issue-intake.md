# Issue 提交入口

`.github/ISSUE_TEMPLATE` 提供三类结构化表单：

- `bug-report.yml`：可复现的软件故障、崩溃和异常行为。
- `feature-request.yml`：基于明确使用场景的功能建议。
- `help-request.yml`：安装、配置、使用方法及尚未确认的故障排查。

`config.yml` 关闭空白 Issue，并提供下载说明、Releases 和私密安全报告入口。错误反馈会收集
完整版本、平台、系统与架构、实际现象、复现步骤和预期结果；日志不是强制项，但公开内容必须
删除 token、签名、Cookie、设备标识和个人数据。表单使用仓库已有的 `错误反馈`、`增强功能`
和 `求助` 标签，不依赖额外的自动分类 Action。

所有公开 Issue 都要求提交者先公开 Star 当前仓库。`issue-star-gate.yml` 在 Issue 新建或
重新打开时查询提交者公开 Star 的仓库列表。首次未通过时发布一条礼貌提醒，Issue 保持开放，
并从提醒创建时间起给予完整 10 分钟宽限期。宽限期结束时再次核验：已 Star 就删除门禁提醒
并保持开放；仍未 Star 才以 `not_planned` 关闭。工作流不读取整个仓库的 stargazer 列表，
也不使用私有源码 Token，只使用当前运行的 `GITHUB_TOKEN` 读取公开资料并写入 Issue。

工作流首次合入 `main` 时会审核当前全部开放 Issue，也支持通过 `workflow_dispatch` 手动
重复审核；Pull Request 不属于审核对象。批量审核并行等待各 Issue 自己的宽限期，隐藏标记
用于避免重复留言，并兼容清理旧版门禁回复；若维护者重新打开一个已关闭 Issue，则旧提醒
会被替换，并从新提醒起重新给予完整 10 分钟。并发配置会取消同一 Issue 的旧等待任务，
防止多个运行重复关闭或留言。查询或写入失败会让 Action 明确失败，不会把普通接口异常
误判成未 Star。

GitHub 对不可公开读取的 Star 列表会返回 `404` 或 `451`，这两种情况按“未公开 Star”处理
并使用同一条温和提醒；限流、网络错误和其他接口故障仍会让 Action 明确失败，避免误处理。

`tests/test_issue_templates.py` 固定表单集合、必需字段、标签、Star 确认项和工作流契约。
