# 番茄小说下载器

番茄小说下载器是一款基于 Rust + Tauri v2 的全平台客户端，用于搜索小说、查看书籍信息、管理书架，并将小说内容下载到本地阅读。

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
- 桌面客户端签名自动更新
- 支持 Windows、Linux、macOS、Android
- Android 可导出并通过系统应用打开 TXT / EPUB
- iOS 提供 **无签名 IPA**，需自行侧载安装（不上架 App Store）

## 下载使用

普通用户建议直接前往本仓库的 Releases 页面下载对应平台的安装包。

发布下载地址：

https://github.com/POf-L/Fanqie-novel-Downloader/releases

当前工作流可以生成：

- Windows x64 / ARM64：NSIS 安装程序
- Linux x64 / ARM64：DEB 与 AppImage（需要 WebKitGTK 4.1）
- macOS Intel / Apple Silicon：APP 与 DMG
- Android：通用 APK / 分架构 APK，以及 AAB
- iOS 提供 **无签名 IPA**（需自行侧载安装，不上架 App Store）

发布文件统一使用 `FanqieNovelDownloader-tauri-` 前缀。Windows 用户应按 CPU 架构选择 x64 或 ARM64 安装程序；Linux 用户可按发行版选择 DEB 或 AppImage；macOS 用户应区分 Intel 与 Apple Silicon。

Android 普通用户下载 APK 即可（优先 `arm64-v8a`），AAB 主要用于应用商店。

iOS 提供的是 **无 Apple 签名** 的 IPA，不支持上架 App Store；有条件的用户可自行侧载安装，安装后需在「设置 → 通用 → VPN 与设备管理」中信任证书。

桌面端稳定 Release 会同时发布签名更新包及 `latest.json`，客户端可直接使用“一键更新”。标记为 prerelease 的版本不会进入稳定版自动更新通道。

## 使用建议

- 下载前先在设置中确认保存目录。
- 如果章节下载速度不稳定，可以适当降低单次请求章节数量。
- 如果书籍信息显示异常，可以在详情页清除缓存后重新加载。
- 遇到网络波动时，可以稍后重试，避免短时间内反复高频请求。

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

## 仓库结构

- **本仓库（公开）**：Releases、Issues 与 GitHub Actions 打包调度；**不包含**业务源码。
- **私有核心源码**：[`POf-L/Fanqie-novel-Downloader-tauri`](https://github.com/POf-L/Fanqie-novel-Downloader-tauri)（Rust + Tauri v2）。
- 历史 Go/Wails 私有仓 `Fanqie-novel-Downloader-actions` 已由 Tauri 版完全替代并下线。

## 说明

请合理使用本工具，并遵守相关平台规则与当地法律法规。
