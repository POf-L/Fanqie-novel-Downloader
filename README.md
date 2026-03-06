# Fanqie-novel-Downloader

这个公开仓库现在仅用于：

- 保留项目公开入口与 Star
- 承载 GitHub Actions 构建与发布流程
- 发布编译后的客户端产物

应用源码已迁移到私有仓库，不再在这里公开展示。

## 当前用途

- 触发 `.github/workflows/build-release.yml`
- 由 Actions 拉取私有源码仓库后进行编译
- 将编译结果上传为 GitHub Artifacts / Releases

## 需要配置的 Secret

在当前公开仓库的 `Settings -> Secrets and variables -> Actions` 中添加：

- `PRIVATE_SOURCE_TOKEN`：用于读取私有仓库 `POf-L/Fanqie-novel-Downloader-actions`

建议该 token 使用 Fine-grained PAT，并仅授予私有源码仓库 `Contents: Read-only` 权限。

## 工作流说明

默认工作流会从以下私有仓库拉取源码：

- `POf-L/Fanqie-novel-Downloader-actions`

如需构建其他分支，可在手动触发 workflow 时填写 `source_ref`。

## 安全说明

- 公开仓库中不保存客户端源码
- 公开仓库中不保存网关地址与 Bearer Token 等敏感配置
- 敏感信息应仅保存在私有源码仓库或 GitHub Secrets 中
