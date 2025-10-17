# Fanqie Novel Downloader

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](./README.md) | [中文](./README_zh.md)

## Overview

Fanqie Novel Downloader is a modern and efficient tool for downloading novels from Fanqie Novel's website. It features a user-friendly graphical interface built with Tkinter, supports asynchronous downloading for high performance, and allows exporting novels to both TXT and EPUB formats. The application also includes an auto-update mechanism to ensure you always have the latest version.

## Features

- **User-Friendly Interface**: A clean and intuitive GUI built with Tkinter for easy operation.
- **High-Performance Downloading**: Utilizes asynchronous requests (`aiohttp`) to download multiple chapters concurrently, significantly improving download speed.
- **Multiple Formats**: Supports saving novels as both TXT and EPUB files.
- **Search Functionality**: Allows users to search for novels by keyword and view results directly within the application.
- **Auto-Updater**: Automatically checks for new releases on GitHub and prompts for updates, ensuring you're always on the latest version.
- **Smart Chapter Resumption**: Keeps track of downloaded chapters and automatically resumes from the last saved point.
- **Customizable Configuration**: Easily configure settings such as download paths, file formats, and request parameters.

## Tech Stack

- **Core Framework**: Python 3.10+
- **GUI**: Tkinter (with `ttk` for modern styling)
- **Networking**: `requests` for synchronous API calls and `aiohttp` for asynchronous chapter downloads.
- **HTML Parsing**: `BeautifulSoup4` for processing chapter content.
- **Ebook Generation**: `ebooklib` for creating EPUB files.
- **Image Handling**: `Pillow` and `pillow-heif` for cover image processing.
- **Packaging**: `PyInstaller` for bundling the application into a standalone executable.

## Architecture

The project is organized into several key modules:

- **`novel_downloader.py`**: The core logic of the application. It includes `APIManager` for interacting with the Fanqie Novel API, `NovelDownloaderAPI` for orchestrating the download process, and functions for handling chapter content and generating files.
- **`gui.py`**: Implements the graphical user interface using Tkinter. It manages user interactions, displays download progress, and integrates the auto-updater.
- **`config.py`**: Centralizes all configuration settings, including API endpoints, request headers, and version information.
- **`updater.py` & `external_updater.py`**: Manages the auto-update process by checking for new releases on GitHub and applying updates.
- **`build_app.py` & `*.spec`**: Scripts and configuration files for building the application with PyInstaller.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/POf-L/Fanqie-novel-Downloader.git
    cd Fanqie-novel-Downloader
    ```

2.  **Create a virtual environment** (recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### GUI Mode

To run the application with its graphical interface, execute the `gui.py` script:

```bash
python gui.py
```

1.  Enter the **Book ID** of the novel you want to download.
2.  Choose a **Save Path** for the downloaded file.
3.  Select the desired **File Format** (TXT or EPUB).
4.  Click **Start Download** to begin.

### Command-Line Interface (CLI)

The application can also be run from the command line for automated workflows:

```bash
python novel_downloader.py --book_id <BOOK_ID> --save_path <PATH> --file_format <FORMAT>
```

- `--book_id`: The ID of the book to download.
- `--save_path` (optional): The directory to save the file. Defaults to the current directory.
- `--file_format` (optional): `txt` or `epub`. Defaults to `txt`.

## Configuration

The application's behavior can be customized through the `config.py` file. Key settings include:

- `max_workers`: The number of concurrent download threads.
- `max_retries`: The number of times to retry a failed download.
- `request_timeout`: The timeout for network requests.
- `api_base_url`: The base URL for the Fanqie Novel API.

## Roadmap

- [ ] Add support for proxy configurations.
- [ ] Implement multi-book batch downloading.
- [ ] Enhance EPUB generation with customizable metadata and styling.
- [ ] Improve error handling and provide more detailed feedback.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
