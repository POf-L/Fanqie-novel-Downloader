# Fanqie Novel Downloader

A modern, efficient downloader for Fanqie Novels, built with Python and a clean, responsive web interface.

## Features

-   **Book Search**: Easily search for books by title or author.
-   **Batch Download**: Download multiple books at once.
-   **Format Support**: Export to **TXT** (plain text) or **EPUB** (e-book) formats.
-   **Cover Art**: Automatically fetches and embeds book covers in EPUB files.
-   **Chapter Selection**: Download full books, specific ranges, or manually selected chapters.
-   **Cross-Platform**: Runs on Windows, macOS, Linux, and Termux (Android).
-   **Modern UI**: Clean, "Apple Flow" inspired interface with dark mode support.

## Installation

### Windows / macOS / Linux

1.  **Download**: Get the latest release from the [Releases](https://github.com/POf-L/Fanqie-novel-Downloader/releases) page.
2.  **Run**:
    -   **Windows**: Run the `.exe` file.
    -   **Linux/macOS**: Grant execution permissions (`chmod +x ...`) and run the binary.

### Source Code (Python)

Requirements: Python 3.7+

1.  Clone the repository:
    ```bash
    git clone https://github.com/POf-L/Fanqie-novel-Downloader.git
    cd Fanqie-novel-Downloader
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Run the application:
    ```bash
    # GUI Mode (Web Interface)
    python main.py

    # CLI Mode (Command Line)
    python novel_downloader.py
    ```

## Usage

1.  **Open the App**: Launch the application to see the web dashboard.
2.  **Search or Enter ID**:
    -   Use the **Search** tab to find books.
    -   Or paste a book URL/ID (e.g., `https://fanqienovel.com/page/123456...`) in the **Download** tab.
3.  **Select Options**: Choose your save path and output format (TXT/EPUB).
4.  **Download**: Click "Start Download" and watch the progress.

## Building from Source

### Standard Build
```bash
pyinstaller main.spec
```

### Termux (Android)
```bash
pkg install python git make clang
pip install -r requirements-termux.txt
python novel_downloader.py
```

## License

This project is for personal study and research purposes only. Please support original authors and official platforms.

[MIT License](LICENSE)
