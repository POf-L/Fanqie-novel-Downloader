# 📚 番茄小说下载器 | Fanqie Novel Downloader

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/POf-L/Fanqie-Tomato-Downloader?style=flat-square&logo=github)](https://github.com/POf-L/Fanqie-Tomato-Downloader/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/POf-L/Fanqie-Tomato-Downloader?style=flat-square&logo=github)](https://github.com/POf-L/Fanqie-Tomato-Downloader/network/members)
[![GitHub issues](https://img.shields.io/github/issues/POf-L/Fanqie-Tomato-Downloader?style=flat-square&logo=github)](https://github.com/POf-L/Fanqie-Tomato-Downloader/issues)
[![GitHub license](https://img.shields.io/github/license/POf-L/Fanqie-Tomato-Downloader?style=flat-square)](LICENSE)
[![GitHub last commit](https://img.shields.io/github/last-commit/POf-L/Fanqie-Tomato-Downloader?style=flat-square)](https://github.com/POf-L/Fanqie-Tomato-Downloader/commits/main)

[![Windows Support](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/POf-L/Fanqie-Tomato-Downloader/releases)
[![MacOS Support](https://img.shields.io/badge/MacOS-000000?style=flat-square&logo=apple&logoColor=white)](https://github.com/POf-L/Fanqie-Tomato-Downloader/releases)
[![Linux Support](https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black)](https://github.com/POf-L/Fanqie-Tomato-Downloader/releases)

**🌟 高效、优雅且功能强大的番茄小说下载解决方案 🌟**

</div>

## ✨ 特性

|  |  |
|---|---|
| **📚 高质量内容获取** | **🔄 多格式转换** |
| * 支持番茄小说全平台内容下载  | * 支持输出纯净 TXT 格式 |
| * 智能解析章节结构与内容 | * 生成精美排版的 EPUB 电子书 |
| * 自动校正小说格式与标点 | * 保留原书籍章节结构 |
| **⚡ 高效下载引擎** | **🖥️ 界面体验** |
| * 多线程并发下载技术 | * 直观友好的图形界面 |
| * 智能调节网络请求频率 | * 实时下载进度可视化 |
| * 断点续传与状态恢复 | * 跨平台一致性体验 |

## 🚀 快速开始

### 🌐 在线下载（零安装，零依赖）

<details>
<summary><b>点击展开详细步骤</b></summary>

利用GitHub Actions的强大功能，无需在本地安装任何软件即可下载小说：

1. 在GitHub仓库页面，点击 **"Actions"** 选项卡
2. 左侧选择 **"在线下载小说"** 工作流
3. 点击 **"Run workflow"** 按钮
4. 填写以下信息：
   - **小说ID**：从番茄小说网址中获取（例如：`https://fanqienovel.com/page/7105916563` 中的 `7105916563`）
   - **下载线程数**：默认为5，可选1-10
   - **输出格式**：选择txt或epub
5. 点击 **"Run workflow"** 开始下载
6. 下载完成后，点击运行记录中的 **"Summary"** 标签
7. 在 **"Artifacts"** 部分找到并下载小说文件（保存期限为7天）

</details>

### 📦 一键式安装与使用

<details>
<summary><b>点击查看各平台预编译版本</b></summary>

从 [📥 官方发布页](https://github.com/POf-L/Fanqie-Tomato-Downloader/releases) 下载适合您系统的预编译版本：

| 平台 | 下载链接 | 说明 |
|------|---------|------|
| Windows | [`Fanqie-Novel-Downloader-Windows.zip`](https://github.com/POf-L/Fanqie-Tomato-Downloader/releases) | 解压后双击运行 `番茄小说下载器.exe` |
| MacOS | [`Fanqie-Novel-Downloader-MacOS.zip`](https://github.com/POf-L/Fanqie-Tomato-Downloader/releases) | 解压后运行 `番茄小说下载器` 应用 |
| Linux | [`Fanqie-Novel-Downloader-Linux.zip`](https://github.com/POf-L/Fanqie-Tomato-Downloader/releases) | 解压后运行 `番茄小说下载器` 可执行文件 |

</details>

### 💻 从源码运行（开发者选项）

<details>
<summary><b>点击展开开发者指南</b></summary>

```bash
# 1. 克隆代码仓库
git clone https://github.com/POf-L/Fanqie-Tomato-Downloader.git
cd Fanqie-Tomato-Downloader

# 2. 安装依赖库
pip install -r requirements.txt

# 3. 启动应用
python gui.py
```

</details>

## 💻 使用指南

### 🔍 如何查找小说ID

在番茄小说网站上，打开您想要下载的小说页面，URL中的数字部分就是小说ID。

> 例如：`https://fanqienovel.com/page/7105916563` 中的 `7105916563` 就是小说ID。

### 📂 下载文件位置

- **GUI应用**：下载的文件保存在您指定的保存路径中
- **在线下载**：文件将作为GitHub Artifacts提供下载，保存期限为7天

## 🛠️ 技术架构

本项目主要使用 Python 和 `customtkinter` 构建。核心模块交互如下：

```mermaid
graph LR
    GUI_Module[GUI_Module (gui.py)\nNovelDownloaderGUI]
    LibraryWindowModule[LibraryWindowModule (library.py)\nLibraryWindow]
    ReaderWindowModule[ReaderWindowModule (reader.py)\nReader]
    SettingsDialogModule[SettingsDialogModule (settings.py)\nSettingsDialog]
    SplashScreenModule[SplashScreenModule (splash.py)\nSplashScreen]

    DownloaderLogic[DownloaderLogic (gui.py)\ndownload_novel,\nstart_download]
    LibraryManager[LibraryManager (library.py)\nload/save/add/remove,\nLibrary Logic]
    ConfigManager[ConfigManager (config.py)\nload/save UserConfig]

    RequestHandlerModule[RequestHandlerModule (request_handler.py)\nRequestHandler,\nget_book_info,\ndown_text,\nextract_chapters]

    UserConfig_JSON[user_config.json\n用户配置]
    LibData_JSON[library.json\n书库数据]
    CookieData_JSON[cookie.json\nCookie]
    NovelFiles[小说文件\n(*.txt, *.epub)]

    GUI_Module --> DownloaderLogic
    GUI_Module --> LibraryWindowModule
    GUI_Module --> SettingsDialogModule
    GUI_Module -- 调用 --> LibraryManager
    GUI_Module -- 调用 --> ConfigManager
    LibraryWindowModule --> LibraryManager
    LibraryWindowModule --> ReaderWindowModule
    ReaderWindowModule --> ConfigManager
    SettingsDialogModule --> ConfigManager

    DownloaderLogic -- 使用 --> RequestHandlerModule
    LibraryManager -- 使用 --> RequestHandlerModule
    LibraryManager -- 操作 --> LibData_JSON
    ConfigManager -- 操作 --> UserConfig_JSON
    RequestHandlerModule -- 获取/更新 --> CookieData_JSON
    DownloaderLogic -- 生成 --> NovelFiles

    style UserConfig_JSON fill:#f9f,stroke:#333,stroke-width:2px
    style LibData_JSON fill:#f9f,stroke:#333,stroke-width:2px
    style CookieData_JSON fill:#f9f,stroke:#333,stroke-width:2px
    style NovelFiles fill:#ccf,stroke:#333,stroke-width:2px
```

*   **UI 层**：`customtkinter` 构建图形界面。
*   **应用逻辑层**：核心业务逻辑，控制下载、书库、配置等。
*   **数据交互层**：`request_handler.py` 负责网络请求和数据处理。
*   **数据存储层**：JSON 和 TXT/EPUB 文件存储数据。

## 🔄 自动化构建

本项目采用 GitHub Actions 进行自动化构建和发布流程，`build-and-release.yml` 描述了详细的构建步骤。

### ⚙️ 自动构建流程

1.  **多平台构建**：支持 Windows, macOS, Linux。
2.  **环境配置**：自动配置 Python 环境和依赖。
3.  **代码编译**：PyInstaller 打包 Python 代码。
4.  **性能优化**：优化体积和性能。
5.  **版本发布**：自动上传到 GitHub Releases 页面。

### 🚀 手动构建与发布

1.  **GitHub Actions 页面**：在仓库 Actions 页面选择 "build-and-release" 工作流。
2.  **运行工作流**：点击 "Run workflow"，填写版本信息。
3.  **等待完成**：等待 GitHub Actions 完成构建和发布。

## ❓ 常见问题

<details>
<summary><b>遇到下载问题？</b></summary>

-   **检查网络**：确保网络连接正常。
-   **线程调整**：尝试在设置中调整下载线程数。
-   **Cookie**：检查或清除 `cookie.json` 文件，重新获取 Cookie。
-   **API 限制**：部分小说可能存在下载限制，请更换其他源或稍后重试。

</details>

<details>
<summary><b>程序启动异常？</b></summary>

-   **版本兼容**：确认下载版本与操作系统匹配。
-   **依赖安装**：源码运行请检查 `requirements.txt` 依赖是否安装完整。
-   **系统环境**：确保系统满足运行最低配置要求。
-   **文件完整性**：尝试重新下载发布版本，避免文件损坏。

</details>

## 📜 许可证

本项目基于 [MIT License](LICENSE) 开源，您可以自由使用和修改。

---

<div align="center">

**⭐ 感谢您的使用，欢迎 Star 项目以支持维护和更新！⭐** 

[GitHub 仓库](https://github.com/POf-L/Fanqie-Tomato-Downloader) | [问题反馈](https://github.com/POf-L/Fanqie-Tomato-Downloader/issues)

</p>
