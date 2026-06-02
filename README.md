# 番茄小说下载器

番茄小说下载器是一款面向普通用户的桌面客户端，用于搜索小说、查看书籍信息、管理书架，并将小说内容下载到本地阅读。

项目目标是尽量做到打开即用，减少命令行和复杂配置，让不熟悉开发环境的用户也能直接使用。

## 软件界面

![番茄小说下载器桌面客户端首页](docs/images/desktop-home.png)

上图为当前桌面客户端首页界面，包含搜索、书架、历史、设置、下载进度与更新入口等常用功能区域。

## 主要功能

- 小说搜索与书籍详情查看
- 书籍封面、作者、状态、简介等信息展示
- 在线阅读与阅读进度记录
- 书架管理
- TXT / EPUB 下载
- 下载历史记录
- 桌面客户端自动更新
- Windows、Linux、macOS 桌面端构建

## 下载使用

普通用户建议直接前往本仓库的 Releases 页面下载对应平台的压缩包。

当前发布产物包括：

- `FanqieNovelDownloader-desktop-windows-x64.zip`
- `FanqieNovelDownloader-desktop-linux-x64.tar.gz`
- `FanqieNovelDownloader-desktop-macos-arm64.tar.gz`
- `FanqieNovelDownloader-desktop-macos-x64.tar.gz`（可选 Intel 构建）

Windows 用户解压后运行 `FanqieNovelDownloader-desktop-windows-x64.exe` 即可。

Linux / macOS 用户解压后运行对应平台的桌面客户端文件。如遇到系统安全提示，请按照系统提示允许应用运行。

## 使用建议

- 下载前先在设置中确认保存目录。
- 如果章节下载速度不稳定，可以适当降低单次请求章节数量。
- 如果书籍信息显示异常，可以在详情页清除缓存后重新加载。
- 遇到网络波动时，可以稍后重试，避免短时间内反复高频请求。

## 手动构建

维护者可以在 GitHub Actions 中手动运行 `Build and Release` 工作流。

可选参数：

- `source_ref`：指定构建使用的分支、Tag 或 Commit
- `publish_release`：是否自动创建 GitHub Release
- `platform_windows_x64`：是否构建 Windows x64
- `platform_linux_x64`：是否构建 Linux x64
- `platform_macos_arm64`：是否构建 macOS arm64
- `platform_macos_x64`：是否构建 macOS Intel x64

构建完成后，产物会上传为 Actions Artifact；如果开启发布，会自动创建 Release。

## 问题反馈

如果使用中遇到问题，可以通过 Issues 反馈。

反馈时建议附带：

- 使用的平台与系统版本
- 下载的发布版本号
- 问题复现步骤
- 报错截图或日志

## 支持与赞助

如果这个项目对你有帮助，也欢迎支持一下合作服务：

> 走邀请码注册即送 **1 美元**，不走邀请链接是没有的。麻烦各位体验一下了。

注册链接：

https://999554.xyz/register?aff=Xf2p

也诚招赞助与推广合作。想要做推广的，也可以通过 Issues 留言、邮箱等方式联系我。

## 说明

请合理使用本工具，并遵守相关平台规则与当地法律法规。
