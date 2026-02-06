# 番茄小说下载器

[![GitHub release](https://img.shields.io/github/release/POf-L/Fanqie-novel-Downloader.svg)](https://github.com/POf-L/Fanqie-novel-Downloader/releases)
[![GitHub stars](https://img.shields.io/github/stars/POf-L/Fanqie-novel-Downloader.svg)](https://github.com/POf-L/Fanqie-novel-Downloader)
[![GitHub license](https://img.shields.io/github/license/POf-L/Fanqie-novel-Downloader.svg)](https://github.com/POf-L/Fanqie-novel-Downloader/blob/main/LICENSE)
[![Build Status](https://github.com/POf-L/Fanqie-novel-Downloader/workflows/Build%20and%20Release/badge.svg)](https://github.com/POf-L/Fanqie-novel-Downloader/actions)

一个现代化、高效的番茄小说下载器，使用 Python 构建，配备简洁、响应式的网页界面。

## ✨ 功能特性

- 📚 **图书搜索**: 轻松按标题或作者搜索图书
- 📦 **批量下载**: 一次下载多本图书
- 📄 **格式支持**: 导出为 **TXT**（纯文本）或 **EPUB**（电子书）格式
- 🖼️ **封面图片**: 自动获取并在 EPUB 文件中嵌入图书封面
- 📖 **章节选择**: 下载完整图书、特定范围或手动选择的章节
- 🌐 **跨平台**: 支持 Windows、macOS、Linux 和 Termux（Android）
- ☁️ **GitHub Actions 云端下载**: 无需本地环境，直接在 GitHub 云端批量下载小说

## 🚀 快速开始

### 方式一：GitHub Actions 云端下载 ☁️ (推荐)

**无需安装任何软件，直接在 GitHub 云端下载小说！**

👉 [**查看云端下载指南**](docs/CLOUD_DOWNLOAD.md)

### 方式二：本地安装使用

👉 [**查看本地安装指南**](docs/LOCAL_INSTALLATION.md)

## 📖 文档导航

| 文档 | 描述 |
| :--- | :--- |
| [📋 README.md](docs/README.md) | 项目概览和快速开始 |
| [☁️ CLOUD_DOWNLOAD.md](docs/CLOUD_DOWNLOAD.md) | GitHub Actions 云端下载详细指南 |
| [💻 LOCAL_INSTALLATION.md](docs/LOCAL_INSTALLATION.md) | 本地安装和使用指南 |
| [📚 USER_GUIDE.md](docs/USER_GUIDE.md) | 详细使用指南和功能说明 |
| [🤖 TERMUX_GUIDE.md](docs/TERMUX_GUIDE.md) | Termux（Android）专用指南 |
| [🤝 CONTRIBUTING.md](docs/CONTRIBUTING.md) | 贡献指南和开发说明 |

## 🏗️ 项目结构

```
Fanqie-novel-Downloader/
├── core/                   # 核心功能模块
│   ├── novel_downloader.py # 小说下载核心逻辑
│   ├── cli.py             # 命令行界面
│   └── state_store.py     # 状态管理
├── web/                    # Web 界面
│   ├── web_app.py         # Flask Web 应用
│   ├── static/            # 静态资源
│   └── templates/         # HTML 模板
├── utils/                  # 工具模块
├── config/                 # 配置文件
├── scripts/                # 脚本文件
├── docs/                   # 文档
└── main.py                 # 主程序入口
```

## 📸 界面预览

### Web 界面
- 🌐 现代化响应式设计
- 🔍 实时搜索功能
- 📊 下载进度显示
- 📱 移动端适配

### 命令行界面
- ⚡ 快速批量操作
- 🎛️ 丰富的参数选项
- 📈 进度条显示
- 🔧 高级配置支持

## 🛠️ 技术栈

- **后端**: Python 3.7+, Flask, aiohttp
- **前端**: HTML5, CSS3, JavaScript (Bootstrap)
- **打包**: PyInstaller (跨平台可执行文件)
- **CI/CD**: GitHub Actions
- **部署**: Docker (可选)

## 📊 下载统计

![GitHub Downloads](https://img.shields.io/github/downloads/POf-L/Fanqie-novel-Downloader/total?color=brightgreen)

## 🔄 更新日志

### 最新版本特性
- ✨ 新增 GitHub Actions 云端下载功能
- 🐛 修复 Termux ARM64 兼容性问题
- 🚀 优化下载速度和稳定性
- 📱 改进移动端界面适配

👉 [查看完整更新日志](CHANGELOG.md)

## 🤝 如何贡献

我们欢迎所有形式的贡献！

👉 [**查看贡献指南**](docs/CONTRIBUTING.md)

### 贡献方式
- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 改进文档
- 🔧 提交代码修复
- 🌟 推广项目

## ❓ 常见问题

### Q: 支持哪些平台？
A: 支持 Windows、macOS、Linux 和 Android (Termux)。

### Q: 下载的小说保存在哪里？
A: 云端下载在 GitHub Actions Artifacts 中，本地下载在程序目录的 `novels/` 文件夹。

### Q: 可以批量下载吗？
A: 可以！支持批量下载多本小说，可设置并发数量。

👉 [查看更多 FAQ](docs/USER_GUIDE.md#常见问题)

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

## ⭐ 支持项目

如果这个项目对你有帮助，请：

- 🌟 给个 Star 支持一下
- 🔄 Fork 并分享给朋友
- 📝 提交反馈和建议
- 💖 [请作者喝杯咖啡](https://github.com/sponsors/POf-L)

## 🔗 相关链接

- [📦 下载页面](https://github.com/POf-L/Fanqie-novel-Downloader/releases)
- [🐛 问题反馈](https://github.com/POf-L/Fanqie-novel-Downloader/issues)
- [💬 讨论区](https://github.com/POf-L/Fanqie-novel-Downloader/discussions)
- [📖 在线文档](https://pof-l.github.io/Fanqie-novel-Downloader/)

---

<div align="center">

**[⬆️ 回到顶部](#番茄小说下载器)**

Made with ❤️ by [POf-L](https://github.com/POf-L)

</div>
