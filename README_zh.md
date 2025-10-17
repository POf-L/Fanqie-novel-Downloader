# 番茄小说下载器

[![Python Version](https://img-shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img-shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](./README.md) | [中文](./README_zh.md)

## 项目概述

番茄小说下载器是一款现代化、高效率的番茄小说下载工具。它拥有一个基于 Tkinter 构建的用户友好图形界面，支持异步下载以实现高性能，并允许将小说导出为 TXT 和 EPUB 两种格式。该应用程序还包含自动更新机制，确保您始终使用最新版本。

## 功能特性

- **用户友好的界面**: 基于 Tkinter 构建的简洁直观的图形用户界面，操作简单。
- **高性能下载**: 利用异步请求（`aiohttp`）并发下载多个章节，显著提升下载速度。
- **多格式支持**: 支持将小说保存为 TXT 和 EPUB 文件。
- **搜索功能**: 允许用户按关键词搜索小说，并直接在应用程序内查看结果。
- **自动更新**: 自动检查 GitHub 上的新版本并提示更新，确保您始终使用最新版本。
- **智能断点续传**: 记录已下载的章节，并自动从上次保存的位置恢复下载。
- **可自定义配置**: 轻松配置下载路径、文件格式和请求参数等设置。

## 技术栈

- **核心框架**: Python 3.10+
- **图形界面**: Tkinter (使用 `ttk` 实现现代化风格)
- **网络请求**: `requests` 用于同步 API 调用，`aiohttp` 用于异步章节下载。
- **HTML 解析**: `BeautifulSoup4` 用于处理章节内容。
- **电子书生成**: `ebooklib` 用于创建 EPUB 文件。
- **图像处理**: `Pillow` 和 `pillow-heif` 用于处理封面图片。
- **打包工具**: `PyInstaller` 用于将应用程序打包成独立的可执行文件。

## 架构

项目由以下几个关键模块组成：

- **`novel_downloader.py`**: 应用程序的核心逻辑。包含与番茄小说 API 交互的 `APIManager`、协调下载过程的 `NovelDownloaderAPI` 以及处理章节内容和生成文件的函数。
- **`gui.py`**: 使用 Tkinter 实现图形用户界面。管理用户交互、显示下载进度并集成自动更新功能。
- **`config.py`**: 集中管理所有配置设置，包括 API 端点、请求头和版本信息。
- **`updater.py` & `external_updater.py`**: 通过检查 GitHub 上的新版本并应用更新来管理自动更新过程。
- **`build_app.py` & `*.spec`**: 用于使用 PyInstaller 构建应用程序的脚本和配置文件。

## 安装

1.  **克隆仓库**:
    ```bash
    git clone https://github.com/POf-L/Fanqie-novel-Downloader.git
    cd Fanqie-novel-Downloader
    ```

2.  **创建虚拟环境** (推荐):
    ```bash
    python -m venv venv
    source venv/bin/activate  # 在 Windows 上, 使用 `venv\Scripts\activate`
    ```

3.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

## 使用方法

### 图形界面模式

要运行带有图形界面的应用程序，请执行 `gui.py` 脚本：

```bash
python gui.py
```

1.  输入您想下载的小说的 **书籍ID**。
2.  为下载的文件选择一个 **保存路径**。
3.  选择所需的 **文件格式** (TXT 或 EPUB)。
4.  点击 **开始下载**。

### 命令行界面 (CLI)

该应用程序也可以从命令行运行，以实现自动化工作流程：

```bash
python novel_downloader.py --book_id <书籍ID> --save_path <路径> --file_format <格式>
```

- `--book_id`: 要下载的书籍的 ID。
- `--save_path` (可选): 保存文件的目录。默认为当前目录。
- `--file_format` (可选): `txt` 或 `epub`。默认为 `txt`。

## 配置

可以通过 `config.py` 文件自定义应用程序的行为。关键设置包括：

- `max_workers`: 并发下载线程数。
- `max_retries`: 失败下载的重试次数。
- `request_timeout`: 网络请求的超时时间。
- `api_base_url`: 番茄小说 API 的基础 URL。

## 路线图

- [ ] 增加代理配置支持。
- [ ] 实现多本书籍的批量下载。
- [ ] 通过可自定义的元数据和样式增强 EPUB 生成。
- [ ] 改进错误处理并提供更详细的反馈。

## 许可证

本项目根据 MIT 许可证授权。详见 [LICENSE](LICENSE) 文件。
