# 番茄小说下载器

基于 **Rust + Tauri v2** 的跨平台小说工具，提供搜索、书籍详情、在线阅读、书架管理，
以及 TXT / EPUB 下载。桌面端与移动端共用同一套前端和 Rust 后端，不依赖 Go sidecar。

[![最新稳定版](https://img.shields.io/github/v/release/POf-L/Fanqie-novel-Downloader?display_name=tag&sort=date)](https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest)
[![仓库校验](https://github.com/POf-L/Fanqie-novel-Downloader/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/POf-L/Fanqie-novel-Downloader/actions/workflows/ci.yml)

- [下载最新稳定版](https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest)
- [查看全部版本](https://github.com/POf-L/Fanqie-novel-Downloader/releases)
- [提交问题或建议](https://github.com/POf-L/Fanqie-novel-Downloader/issues/new/choose)

## 界面预览

当前版本的桌面端与移动端共用同一套界面：主页面提供搜索、详情和书架，详情页及本地/
官方书架卡片都可以通过“清理本书”分别清除临时缓存或删除离线正文；阅读器支持章节目录、
字号/主题调整和可选的沉浸模式。Android 与 iOS 的导出、分享和系统文件访问会根据平台
能力显示对应入口。

## 主要功能

- 通过关键词、番茄小说链接或书籍 ID 搜索和直接载入书籍
- 查看封面、作者、分类、字数、状态、简介和章节目录
- 应用内在线阅读和独立离线书库：可缓存整本章节、查看缓存进度、继续未完成任务、更新或删除离线正文
- 阅读器支持章节切换、阅读主题与字号调整、阅读进度记录，以及默认关闭的沉浸阅读模式
- 记录本机有效阅读时长；官方书架中的书籍会在登录后按已核实的章节、索引和比例字段尝试同步
- 本地和官方书架管理；每张卡片都可继续阅读、发起下载或打开“清理本书”
- 单本下载与批量导入，支持指定章节范围
- 下载任务暂停、继续、取消，以及失败或缺失章节重试
- 导出 TXT / EPUB，保存下载历史并检查本地文件状态；历史页可多选并批量删除导出文档
- Windows 安装版/便携版、Linux DEB/AppImage 和 macOS APP 按发行形态精确匹配更新包；Android、iOS 保留新版本检查与手动下载
- 浅色 / 深色主题，以及中文、English、Русский 界面
- Android 共享目录导出和系统阅读器打开，阅读顶栏会避开状态栏与安全区；iOS 文件导出与系统分享

官方账号返回的累计阅读时间与应用记录的本机累计阅读时长是两套独立数据。本机阅读进度、
阅读时长、书架和离线正文保存在设备上；退出官方账号只删除本机凭据和官方书架缓存，
不会删除这些本地数据。“清除临时缓存”只清理本次运行中的详情、目录和已读章节缓存，
这些内容重启后也会自动消失，不会释放离线书库空间；“删除离线正文”会删除
`<app-data>/offline-books/<book-id>`，但保留书架、阅读进度、阅读时长和已经导出的 TXT/EPUB。

## 下载与平台支持

普通用户应优先从[最新稳定版](https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest)
下载。每个 Release 的说明会列出实际附件、签名状态、安装限制和校验文件；没有发布的
平台或架构不要使用其他安装包代替。

| 平台 | 支持架构 | 普通用户选择 | 当前发布方式 |
| --- | --- | --- | --- |
| Windows | x64、ARM64 | 安装版选 `windows-*-setup.exe`；免安装使用选 `windows-*-portable.exe` | 两种形态都支持自动更新和手动下载，且不会互相转换 |
| Linux | x64、ARM64 | Debian / Ubuntu 选 `.deb`，其他发行版可选 `.AppImage` | DEB 与 AppImage 只更新到相同包类型 |
| Android | arm64-v8a、armeabi-v7a、x86_64、universal | 优先 `arm64-v8a.apk`，不确定架构时选 `universal.apk` | 稳定版；应用内提示新版本；Android 7.0 / API 24 起 |
| macOS | Intel、Apple Silicon | 对应架构的 DMG 或 APP ZIP | APP 形态只接收同架构 APP 更新；无 Apple 签名时仍会受 Gatekeeper 限制 |
| iOS | ARM64 | 无签名 IPA | 应用内提示新版本；需要自行侧载；不上架 App Store |

### Windows

大多数电脑选择 `x64`，Windows on ARM 设备选择 `ARM64`。安装版会运行 NSIS 安装器并
保留安装目录和卸载信息；便携版会在退出后原位覆盖当前 exe，再从原路径重启，不会创建
安装目录、快捷方式或卸载项。两者的自动更新目标是分开的，客户端无法可靠识别发行形态
时只会提供手动下载，不会猜测另一个安装包。

在本次修复之前发布的旧便携版无法安全区分安装包与便携包，需要从最新 Release 手动下载
一次同架构 `windows-*-portable.exe`，关闭程序后覆盖旧文件；完成这次迁移后即可使用便携版
原位自动更新。不要用 `setup.exe` 覆盖便携版，也不要把 portable 附件当作安装器运行。

当前安装程序尚未配置 Windows Authenticode 发行商证书，因此 Windows 可能提示“未知发布者”
或触发 SmartScreen。Release 中的 Tauri/Minisign updater 签名用于证明自动更新包来自项目并且
未被篡改；它与 Windows 展示“已验证的发布者”的 Authenticode 证书不是同一种签名。安装或
手动覆盖前仍应核对 Release 中的 SHA-256 校验清单。

### Linux

桌面壳依赖 **WebKitGTK 4.1**。AppImage 首次运行前需要授予执行权限：

```bash
chmod +x FanqieNovelDownloader-tauri-linux-*.AppImage
```

具体是否同时提供 DEB 与 AppImage，以对应 Release 的实际附件为准。应用内更新只会选择与
当前运行包类型及架构完全一致的元数据条目；缺少专用条目时会转为手动下载，不会从 DEB
切换到 AppImage，反之亦然。

### Android

APK 可以直接安装；AAB 是应用商店上传产物，不能像 APK 一样直接打开安装。应用通过
Android 系统目录选择器保存 TXT / EPUB，并可交给已安装的阅读器打开。安装 APK 时需要
允许当前文件管理器或浏览器安装未知来源应用。

### macOS

Apple Silicon 选择 `arm64`，Intel 选择 `x64`，通常优先下载 DMG。全平台正式 Release 中的
APP updater 只选择同架构 `-app` 条目；历史上单独发布、没有 updater 元数据的“macOS 未签名版”
prerelease 仍需手动下载覆盖。

首次启动被 Gatekeeper 拦截时，先核对 SHA-256，再前往“系统设置 → 隐私与安全性”选择
“仍要打开”。只有 Release 说明明确要求时，才对本应用单独移除隔离属性；不需要全局
关闭 Gatekeeper。当前全平台无签名正式版使用独立的 `unsigned` 更新通道；系统/厂商签名仍然缺失，
但 updater 包由项目 Minisign 密钥校验。历史上没有 `latest.json` 的无签名包仍需手动覆盖安装。

### iOS

iOS 提供的是无 Apple 签名 IPA，需要使用 AltStore、Sideloadly 或其他受信任方式自行
侧载。安装后可能需要在“设置 → 通用 → VPN 与设备管理”中信任对应证书。它不属于
App Store 或 TestFlight 正式发布。

## 基本使用

1. 安装与系统架构匹配的版本。
2. 在“设置”中选择默认保存目录和 TXT / EPUB 格式。
3. 使用关键词搜索，或直接粘贴番茄小说链接、书籍 ID。
4. 在详情页选择在线阅读、缓存离线正文、加入书架、全本下载或章节范围下载；需要释放空间时，
   可在详情页或任一书架卡片点击“清理本书”。
5. 从任务面板管理下载或离线缓存进度；离线缓存完成后，即使没有网络也可以在应用内阅读。
6. 在“历史”中查看或打开已导出的文件；需要批量释放导出文件空间时，勾选记录后点击
   “删除选中文档”。“清空记录”只删除历史条目，不删除磁盘文件。

遇到网络超时或上游接口暂时不可用时，请等待一段时间再重试，避免短时间内连续发起大量
请求。诊断日志默认关闭；需要排查时可在设置中临时开启，日志会对接口参数、签名、Cookie
和书籍标识进行脱敏。

## 常见问题

**macOS 提示应用已损坏**

这通常是未签名、未公证应用被 Gatekeeper 拦截，不表示下载文件一定损坏。请确认架构、
核对校验和，并按对应 Release 的安装说明处理。

**Linux 无法启动**

先确认系统已安装 WebKitGTK 4.1 运行库；AppImage 还需要执行权限。不同发行版的软件包
名称不同，请使用发行版自己的包管理器查询。

**搜索或下载持续超时**

先确认正在使用最新稳定版，并排除代理、私有 DNS、防火墙或网络波动。仍可复现时，提交
错误反馈并附上脱敏后的完整错误文本、平台、版本和复现步骤。

**Android 找不到下载文件**

请在应用内重新选择共享目录并保留系统授予的访问权限。导出完成后可从历史记录打开文件，
或在系统文件管理器中进入所选目录查看。

**“清除临时缓存”和“删除离线正文”有什么区别**

临时缓存只服务于当前运行中的详情、目录和章节访问，最多保留约 10 分钟，关闭应用也会消失；
它不会删除磁盘上的离线正文。删除离线正文会释放该书离线书库占用的空间，同时使相关临时缓存
失效，但不会移除本地/官方书架记录、阅读进度、阅读时长或已导出的 TXT/EPUB。正在缓存该书时，
请先取消对应离线任务，再删除离线正文。

**“删除选中文档”和“清空记录”有什么区别**

“删除选中文档”会删除勾选记录对应的 TXT/EPUB 文件，并在成功后移除对应历史条目；文件已经
不存在时也会清理失效记录。出于安全考虑，目录、符号链接和非 TXT/EPUB 文件不会被删除。
“清空记录”只清空应用内历史，不触碰本地或 Android 系统目录中的导出文件。两项操作都不会
影响书架、阅读进度、阅读时长或离线正文。

**便携版更新后为什么不能变成安装版**

新版本会先识别当前 Windows 发行形态：正常安装目录中的 NSIS 版本只选择 `-nsis`，原始便携
exe 或被复制到其他目录的兼容形态只选择 `-portable`。找不到精确附件或签名时只提供 Release
页面。旧便携版需要按上面的 Windows 说明手动覆盖一次修复版。

## 问题反馈

请从 [Issue 提交入口](https://github.com/POf-L/Fanqie-novel-Downloader/issues/new/choose)
选择“错误反馈”“功能建议”或“使用求助”。仓库不接受空白 Issue，结构化表单会收集版本、
平台、架构、复现步骤和必要的诊断信息。

提交 Issue 前需要先公开 Star 当前项目。Issue 创建或重新打开后会由 Actions 自动核验；
未通过时会先收到礼貌提醒，Issue 在 10 分钟宽限期内保持开放。宽限期内核验通过后，
提醒会自动删除且 Issue 继续开放；超过 10 分钟仍未公开 Star 才会以 `not planned` 关闭。

公开内容中请删除 token、签名、Cookie、设备标识和其他个人数据。安全漏洞请使用
[私密漏洞报告](https://github.com/POf-L/Fanqie-novel-Downloader/security/advisories/new)，
不要创建公开 Issue。

## 支持与赞助

如果这个项目对你有帮助，也欢迎自愿通过下面的合作服务支持项目维护。

> 这是推广邀请链接。合作方目前标注通过该链接注册可获 **1 美元**，项目方也可能获得
> 推广收益；是否使用该链接不影响软件功能、Issue 受理或问题处理。

注册链接：<https://999554.xyz/register?aff=Xf2p>

赞助与推广合作请通过[仓库所有者主页](https://github.com/POf-L)公开的联系方式沟通，
不要提交为产品 Issue。

## 项目边界

- **当前公开仓库**：负责 Releases、Issues、用户文档与 GitHub Actions 发布调度。
- **Rust / Tauri 核心源码**：位于私有 `Fanqie-novel-Downloader-tauri` 仓库；发布时只在
  临时 GitHub Runner 中只读检出，不复制到本公开仓库。
- **发布产物**：仅包含允许列表中的安装包、便携程序、更新签名、校验清单和必要的发布元数据；
  发布前会核对附件清单并扫描 ZIP/TAR 包，拒绝私有检出目录、Rust 源码、源码映射、调试符号、
  凭据和未知文件。

发布由 GitHub Actions 按仓库中的工作流执行。参与贡献前请阅读
[`CONTRIBUTING.md`](CONTRIBUTING.md) 与 [`SECURITY.md`](SECURITY.md)。

## 使用声明

请合理使用本工具，并遵守相关平台规则与当地法律法规。项目不保证上游接口永久可用，
也不建议将自动化下载用于高频、批量滥用或侵犯他人权益的场景。
