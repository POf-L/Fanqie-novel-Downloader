# TomatoNovelDownloader Termux 使用指南

## 📋 系统要求

- **Android**: 7.0+ (Nougat 及以上)
- **Termux**: 最新版本 (推荐从 F-Droid 下载)
- **架构**: ARM64 (aarch64) - 大多数现代 Android 设备
- **存储空间**: 至少 100MB 可用空间

## 🚀 安装步骤

### 1. 安装 Termux

```bash
# 从 F-Droid 安装 Termux (推荐)
# 或者从 GitHub Releases 下载 APK

# 首次运行 Termux，更新包管理器
pkg update && pkg upgrade -y
```

### 2. 安装必要的系统依赖

```bash
# 安装基础运行时依赖
pkg install -y python libffi openssl libjpeg-turbo libwebp libxml2 libxslt

# 安装文件管理工具 (可选)
pkg install -y curl wget unzip
```

### 3. 下载程序

```bash
# 创建程序目录
mkdir -p ~/tomato-novel
cd ~/tomato-novel

# 下载最新版本的 ARM64 可执行文件
# 替换 URL 为最新的 Release 下载链接
wget https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest/download/TomatoNovelDownloader-termux-arm64

# 或者使用 curl
curl -L -o TomatoNovelDownloader-termux-arm64 https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest/download/TomatoNovelDownloader-termux-arm64
```

### 4. 设置执行权限

```bash
# 添加执行权限
chmod +x TomatoNovelDownloader-termux-arm64

# 验证权限
ls -la TomatoNovelDownloader-termux-arm64
```

## 🛠️ 使用方法

### 基本用法

```bash
# 显示帮助信息
./TomatoNovelDownloader-termux-arm64 --help

# 下载单本小说 (替换 BOOK_ID 为实际的书籍ID)
./TomatoNovelDownloader-termux-arm64 download 7372503659137005093

# 批量下载多本小说
./TomatoNovelDownloader-termux-arm64 batch-download "7372503659137005093 7372528691033300280" --format txt

# 指定保存路径
./TomatoNovelDownloader-termux-arm64 download 7372503659137005093 --path ~/storage/shared/Novels
```

### 高级用法

```bash
# 下载为 EPUB 格式
./TomatoNovelDownloader-termux-arm64 download 7372503659137005093 --format epub

# 设置并发下载数量
./TomatoNovelDownloader-termux-arm64 batch-download "BOOK_ID1 BOOK_ID2" --concurrent 5

# 启用详细输出
./TomatoNovelDownloader-termux-arm64 download 7372503659137005093 --verbose
```

## 🔧 故障排除

### 问题 1: "cannot execute: required file not found"

**原因**: 动态链接库缺失或 ELF 解释器路径不正确

**解决方案**:

```bash
# 方法 1: 使用启动脚本 (推荐)
wget https://raw.githubusercontent.com/POf-L/Fanqie-novel-Downloader/main/scripts/termux_launcher.sh
chmod +x termux_launcher.sh
./termux_launcher.sh

# 方法 2: 手动安装依赖
pkg install -y libffi openssl libjpeg-turbo libwebp libxml2 libxslt
export LD_LIBRARY_PATH="/data/data/com.termux/files/usr/lib:$LD_LIBRARY_PATH"
./TomatoNovelDownloader-termux-arm64 --help
```

### 问题 2: "Permission denied"

**解决方案**:

```bash
# 确保文件有执行权限
chmod +x TomatoNovelDownloader-termux-arm64

# 如果仍然失败，检查文件所有者
ls -la TomatoNovelDownloader-termux-arm64
```

### 问题 3: 程序运行缓慢

**优化建议**:

```bash
# 增加并发数量 (根据设备性能调整)
./TomatoNovelDownloader-termux-arm64 batch-download "BOOK_IDS" --concurrent 3

# 关闭不必要的后台应用
# 确保设备有足够的存储空间
```

### 问题 4: 网络连接问题

**解决方案**:

```bash
# 检查网络连接
ping -c 3 qkfqapi.vv9v.cn

# 如果使用代理，设置环境变量
export http_proxy=http://your-proxy:port
export https_proxy=http://your-proxy:port
```

## 📁 文件管理

### 默认保存位置

```bash
# 默认下载目录
~/tomato-novel/novels/

# 访问外部存储 (需要授权)
# 在 Termux 中运行:
termux-setup-storage

# 然后可以访问:
~/storage/shared/  # 内部存储
~/storage/external-1/  # SD卡 (如果有)
```

### 文件格式

- **TXT**: 纯文本格式，体积小，兼容性好
- **EPUB**: 电子书格式，支持目录和样式，推荐阅读器使用

## 🔄 更新程序

```bash
# 备份当前配置和下载的小说
cp -r ~/tomato-novel/novels ~/tomato-novel-backup/

# 下载最新版本
cd ~/tomato-novel
wget -O TomatoNovelDownloader-termux-arm64.new https://github.com/POf-L/Fanqie-novel-Downloader/releases/latest/download/TomatoNovelDownloader-termux-arm64

# 替换旧版本
mv TomatoNovelDownloader-termux-arm64.new TomatoNovelDownloader-termux-arm64
chmod +x TomatoNovelDownloader-termux-arm64

# 验证更新
./TomatoNovelDownloader-termux-arm64 --version
```

## 📚 常用命令参考

### 书籍操作

```bash
# 获取书籍信息
./TomatoNovelDownloader-termux-arm64 info 7372503659137005093

# 下载整本书
./TomatoNovelDownloader-termux-arm64 download 7372503659137005093

# 下载指定章节范围
./TomatoNovelDownloader-termux-arm64 download 7372503659137005093 --chapter-start 1 --chapter-end 50
```

### 批量操作

```bash
# 从文件读取书籍ID列表
echo "7372503659137005093\n7372528691033300280" > book_list.txt
./TomatoNovelDownloader-termux-arm64 batch-download --input-file book_list.txt

# 设置全局配置
./TomatoNovelDownloader-termux-arm64 config --set concurrent_downloads=3
./TomatoNovelDownloader-termux-arm64 config --set default_format=epub
```

## 🐛 调试模式

```bash
# 启用详细日志
./TomatoNovelDownloader-termux-arm64 download 7372503659137005093 --verbose

# 查看程序版本和构建信息
./TomatoNovelDownloader-termux-arm64 --version

# 检查系统环境
./termux_launcher.sh --check-only
```

## 📞 获取帮助

如果遇到问题，请按以下步骤操作：

1. **查看日志**: 使用 `--verbose` 参数运行程序
2. **检查环境**: 运行 `./termux_launcher.sh --check-only`
3. **搜索已知问题**: 查看 [GitHub Issues](https://github.com/POf-L/Fanqie-novel-Downloader/issues)
4. **提交新问题**: 包含以下信息：
   - Android 版本
   - Termux 版本
   - 设备架构 (`uname -m`)
   - 错误信息和日志

## 📄 许可证

本项目遵循 MIT 许可证。详见 [LICENSE](../LICENSE) 文件。
