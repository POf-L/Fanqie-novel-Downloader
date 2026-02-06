# 💻 本地安装使用指南

本文档详细介绍如何在本地安装和使用番茄小说下载器。

## 📋 系统要求

### 最低要求
- **操作系统**: Windows 10+, macOS 10.14+, Ubuntu 18.04+
- **Python**: 3.7 或更高版本
- **内存**: 至少 2GB RAM
- **存储空间**: 至少 500MB 可用空间
- **网络**: 稳定的互联网连接

### 推荐配置
- **操作系统**: Windows 11, macOS 12+, Ubuntu 20.04+
- **Python**: 3.9 或更高版本
- **内存**: 4GB+ RAM
- **存储空间**: 2GB+ 可用空间

## 🚀 安装方式

### 方式一：下载可执行文件（推荐）

#### Windows

1. **下载文件**
   - 访问 [发布页面](https://github.com/POf-L/Fanqie-novel-Downloader/releases)
   - 下载 `TomatoNovelDownloader-Standalone.exe`（推荐，内置运行库）
   - 或下载 `TomatoNovelDownloader.exe`（需要系统安装 WebView2）

2. **运行程序**
   - 双击 `.exe` 文件启动
   - 首次运行可能需要几秒钟初始化
   - 程序会自动在浏览器中打开 Web 界面

3. **Windows Defender 警告**
   - 如果出现安全警告，点击"更多信息" → "仍要运行"
   - 这是误报，程序完全安全

#### macOS

1. **下载文件**
   - 从发布页面下载 `TomatoNovelDownloader-macos`
   - 确保下载了 Intel 版本（非 Apple Silicon）

2. **设置权限**
   ```bash
   chmod +x TomatoNovelDownloader-macos
   ```

3. **运行程序**
   ```bash
   ./TomatoNovelDownloader-macos
   ```

4. **macOS 安全警告**
   - 如果出现"无法打开因为来自身份不明的开发者"
   - 系统偏好设置 → 安全性与隐私 → 通用 → 允许从以下位置下载的 App
   - 点击"仍要打开"

#### Linux

1. **下载文件**
   - 从发布页面下载 `TomatoNovelDownloader-linux`

2. **安装依赖**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y libgtk-3-0 libwebkit2gtk-4.0-37
   
   # CentOS/RHEL/Fedora
   sudo yum install -y gtk3 webkit2gtk3
   # 或 (较新版本)
   sudo dnf install -y gtk3 webkit2gtk3
   ```

3. **设置权限并运行**
   ```bash
   chmod +x TomatoNovelDownloader-linux
   ./TomatoNovelDownloader-linux
   ```

### 方式二：从源代码安装

#### 1. 克隆仓库

```bash
git clone https://github.com/POf-L/Fanqie-novel-Downloader.git
cd Fanqie-novel-Downloader
```

#### 2. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

#### 3. 安装依赖

```bash
# 安装基础依赖
pip install -r config/requirements.txt

# 如果需要开发环境
pip install -r config/requirements-dev.txt
```

#### 4. 运行程序

```bash
# GUI 模式（推荐）
python main.py

# CLI 模式
python core/cli.py --help
```

## 🖥️ 使用方法

### GUI 界面使用

1. **启动程序**
   ```bash
   # 可执行文件
   ./TomatoNovelDownloader
   
   # 或源代码
   python main.py
   ```

2. **打开浏览器**
   - 程序启动后会自动打开默认浏览器
   - 或手动访问 `http://localhost:5000`

3. **搜索书籍**
   - 在搜索框输入书名或作者名
   - 点击搜索按钮或按 Enter
   - 从搜索结果中选择要下载的书籍

4. **配置下载**
   - 选择输出格式（TXT/EPUB）
   - 选择章节范围（全部/自定义范围）
   - 设置保存路径（可选）

5. **开始下载**
   - 点击下载按钮
   - 查看下载进度
   - 下载完成后在保存路径找到文件

### CLI 命令行使用

#### 基本命令

```bash
# 查看帮助
python core/cli.py --help

# 搜索书籍
python core/cli.py search "斗破苍穹"

# 查看书籍信息
python core/cli.py info 7372503659137005093

# 下载单本书籍
python core/cli.py download 7372503659137005093 --format txt

# 批量下载
python core/cli.py batch-download 7372503659137005093 7372528691033300280 --format epub --concurrent 3
```

#### 高级参数

```bash
# 指定保存路径
python core/cli.py download 7372503659137005093 --path ~/Downloads/novels

# 下载指定章节范围
python core/cli.py download 7372503659137005093 --chapter-start 1 --chapter-end 50

# 启用详细输出
python core/cli.py download 7372503659137005093 --verbose

# 设置代理
python core/cli.py download 7372503659137005093 --proxy http://127.0.0.1:8080

# 设置超时时间
python core/cli.py download 7372503659137005093 --timeout 30
```

## 📁 文件结构

### 程序目录结构

```
Fanqie-novel-Downloader/
├── main.py                 # 主程序入口
├── core/                   # 核心功能
│   ├── novel_downloader.py # 下载器核心
│   ├── cli.py             # 命令行界面
│   └── state_store.py     # 状态管理
├── web/                    # Web 界面
│   ├── web_app.py         # Flask 应用
│   ├── static/            # 静态资源
│   └── templates/         # HTML 模板
├── utils/                  # 工具模块
├── config/                 # 配置文件
└── novels/                 # 默认下载目录
```

### 下载文件结构

```
novels/
├── [书名]/
│   ├── [书名].txt         # TXT 格式
│   ├── [书名].epub        # EPUB 格式
│   └── cover.jpg          # 封面图片（如果有）
└── ...
```

## ⚙️ 配置说明

### 配置文件位置

- **Windows**: `%APPDATA%/TomatoNovelDownloader/config.json`
- **macOS**: `~/Library/Application Support/TomatoNovelDownloader/config.json`
- **Linux**: `~/.config/TomatoNovelDownloader/config.json`

### 主要配置项

```json
{
  "download": {
    "default_format": "txt",
    "default_path": "./novels",
    "concurrent_limit": 3,
    "timeout": 30,
    "retry_times": 3
  },
  "ui": {
    "theme": "light",
    "language": "zh-CN"
  },
  "network": {
    "proxy": null,
    "user_agent": "TomatoNovelDownloader/1.0"
  }
}
```

### 环境变量

```bash
# 设置代理
export HTTP_PROXY=http://127.0.0.1:8080
export HTTPS_PROXY=http://127.0.0.1:8080

# 设置下载路径
export TOMATO_DOWNLOAD_PATH=/path/to/downloads

# 设置并发数
export TOMATO_CONCURRENT_LIMIT=5
```

## 🔧 故障排除

### Windows 问题

#### 问题1：程序无法启动

**解决方案**：
1. 确保下载了正确版本（Standalone 版本推荐）
2. 安装 [Microsoft Visual C++ Redistributable](https://docs.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
3. 检查 Windows Defender 是否误报

#### 问题2：WebView2 相关错误

**解决方案**：
1. 下载 Standalone 版本（内置 WebView2）
2. 或安装 [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)

#### 问题3：端口被占用

**解决方案**：
1. 关闭其他使用 5000 端口的程序
2. 或修改端口：`python main.py --port 5001`

### macOS 问题

#### 问题1：无法打开身份不明的开发者

**解决方案**：
```bash
# 临时允许
sudo spctl --master-disable

# 或添加例外
xattr -d com.apple.quarantine TomatoNovelDownloader-macos
```

#### 问题2：缺少动态库

**解决方案**：
```bash
# 安装 Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装依赖
brew install python3 gtk+3 webkit2gtk
```

### Linux 问题

#### 问题1：缺少 GTK 或 WebKit

**解决方案**：
```bash
# Ubuntu/Debian
sudo apt-get install -y libgtk-3-0 libwebkit2gtk-4.0-37 libgconf-2-4

# CentOS/RHEL/Fedora
sudo yum install -y gtk3 webkit2gtk3 GConf2
# 或
sudo dnf install -y gtk3 webkit2gtk3 GConf2
```

#### 问题2：权限问题

**解决方案**：
```bash
# 确保可执行权限
chmod +x TomatoNovelDownloader-linux

# 如果仍然无法运行
sudo chown $USER:$USER TomatoNovelDownloader-linux
```

### 通用问题

#### 问题1：网络连接失败

**解决方案**：
1. 检查网络连接
2. 尝试使用代理
3. 检查防火墙设置
4. 更换 DNS（如 8.8.8.8）

#### 问题2：下载速度慢

**解决方案**：
1. 减少并发数
2. 检查网络带宽
3. 尝试不同时间段下载
4. 使用 CLI 模式（通常更快）

#### 问题3：内存占用过高

**解决方案**：
1. 减少并发下载数量
2. 分批下载大量书籍
3. 关闭其他占用内存的程序

## 🔄 更新程序

### 可执行文件更新

1. **下载新版本**
   - 访问发布页面下载最新版本
   - 备份当前配置和下载文件

2. **替换程序**
   ```bash
   # 备份
   cp -r novels novels_backup
   
   # 替换程序文件
   # Windows: 直接替换 exe 文件
   # macOS/Linux: 替换可执行文件
   ```

3. **验证更新**
   ```bash
   ./TomatoNovelDownloader --version
   ```

### 源代码更新

```bash
# 拉取最新代码
git pull origin main

# 更新依赖
pip install -r config/requirements.txt --upgrade

# 运行程序
python main.py
```

## 📚 更多资源

- [📖 详细使用指南](USER_GUIDE.md)
- [🤖 Termux 指南](TERMUX_GUIDE.md)
- [🤝 贡献指南](CONTRIBUTING.md)
- [🐛 问题反馈](https://github.com/POf-L/Fanqie-novel-Downloader/issues)

---

📖 **返回主文档**: [README.md](../README.md)
