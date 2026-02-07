# TomatoNovelDownloader Termux 使用指南

## 📋 系统要求

- **Android**: 7.0+ (Nougat 及以上)
- **Termux**: 最新版本（推荐 F-Droid 版本）
- **架构**: ARM64 (`aarch64`)
- **网络**: 可访问 GitHub Releases

## 🚀 推荐安装（修复 `cannot execute: required file not found`）

> 从 `2026.02.01` 起，Termux 平台建议使用 **脚本入口 + Launcher + Runtime** 架构。  
> `TomatoNovelDownloader-termux-arm64` 现在是 shell 启动脚本，不再依赖旧 ELF 可执行文件。

### 1) 准备 Termux 环境

```bash
pkg update && pkg upgrade -y
pkg install -y python curl
```

### 2) 下载 Termux 入口文件

```bash
mkdir -p ~/tomato-novel
cd ~/tomato-novel

wget https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest/download/TomatoNovelDownloader-termux-arm64
# 或：curl -L -o TomatoNovelDownloader-termux-arm64 \
#   https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest/download/TomatoNovelDownloader-termux-arm64

chmod +x TomatoNovelDownloader-termux-arm64
```

### 3) 首次启动

```bash
./TomatoNovelDownloader-termux-arm64
```

首次启动会自动：
- 检查 Termux 与 Python 环境
- 下载 `launcher.py`
- 按 `termux-arm64` 平台下载并校验 `runtime-termux-arm64.zip`
- 解压到本地缓存目录并启动程序

## 🛠️ 常用命令

```bash
# 查看脚本帮助
./TomatoNovelDownloader-termux-arm64 --help

# 仅检查环境
./TomatoNovelDownloader-termux-arm64 --check-only

# 强制更新 launcher.py
./TomatoNovelDownloader-termux-arm64 --update-launcher
```

## 🔧 故障排除

### 问题 1: `cannot execute: required file not found`

**典型原因**：你拿到的是旧版 ELF 二进制，Android/Termux 下找不到其解释器或运行库。  
**修复方式**：重新下载当前 release 的 `TomatoNovelDownloader-termux-arm64`（脚本入口）。

```bash
cd ~/tomato-novel
rm -f TomatoNovelDownloader-termux-arm64
wget https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest/download/TomatoNovelDownloader-termux-arm64
chmod +x TomatoNovelDownloader-termux-arm64
./TomatoNovelDownloader-termux-arm64 --check-only
```

### 问题 2: 下载 launcher/runtime 失败

```bash
# 检查 GitHub 连通性
curl -I https://github.com

# 更新基础网络工具
pkg install -y ca-certificates curl
```

如处于特殊网络环境，请先配置代理环境变量再运行脚本：

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

### 问题 3: 需要清理本地缓存重新拉取

```bash
rm -rf ~/.fanqienoveldownloader/runtime
rm -f ~/.fanqienoveldownloader/launcher_state.json
./TomatoNovelDownloader-termux-arm64
```

## 🔄 更新方式

```bash
cd ~/tomato-novel
wget -O TomatoNovelDownloader-termux-arm64.new \
  https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest/download/TomatoNovelDownloader-termux-arm64
mv TomatoNovelDownloader-termux-arm64.new TomatoNovelDownloader-termux-arm64
chmod +x TomatoNovelDownloader-termux-arm64
./TomatoNovelDownloader-termux-arm64 --check-only
```

## 📞 获取帮助

提交 Issue 时建议附带以下信息：
- Android 版本
- Termux 版本
- 架构输出：`uname -m`
- 执行日志（尤其是 `--check-only` 输出）

Issues: https://github.com/POf-L/Fanqie-novel-Downloader/issues

