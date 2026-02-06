# 📚 详细使用指南

本文档详细介绍番茄小说下载器的所有功能和使用方法。

## 📋 目录

- [界面介绍](#界面介绍)
- [搜索功能](#搜索功能)
- [下载功能](#下载功能)
- [格式说明](#格式说明)
- [高级功能](#高级功能)
- [命令行详解](#命令行详解)
- [配置管理](#配置管理)
- [常见问题](#常见问题)

## 🖥️ 界面介绍

### Web 界面布局

```
┌─────────────────────────────────────────────────────┐
│  🍅 番茄小说下载器                    [设置] [关于]  │
├─────────────────────────────────────────────────────┤
│  🔍 搜索框: [输入书名或作者]      [搜索按钮]        │
├─────────────────────────────────────────────────────┤
│  📚 搜索结果区域                                      │
│  ┌─────────┬─────────────┬─────────┬─────────────┐   │
│  │ 封面    │ 书名        │ 作者    │ 操作        │   │
│  │ 图片    │             │         │ [下载]      │   │
│  └─────────┴─────────────┴─────────┴─────────────┘   │
├─────────────────────────────────────────────────────┤
│  ⬇️ 下载队列                                         │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 📖 [书名] - 进度: 85%  [暂停] [取消]            │ │
│  └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────┤
│  📊 下载统计: 总计: 5 | 成功: 4 | 失败: 1          │
└─────────────────────────────────────────────────────┘
```

### 主要功能区域

1. **搜索区域**: 输入书名、作者名进行搜索
2. **结果区域**: 显示搜索结果，包含书籍信息和操作按钮
3. **下载队列**: 显示当前下载任务和进度
4. **统计信息**: 显示下载统计数据

## 🔍 搜索功能

### 基本搜索

在搜索框中输入：
- **书名**: 如 "斗破苍穹"、"完美世界"
- **作者名**: 如 "天蚕土豆"、"辰东"
- **关键词**: 如 "玄幻"、"修仙"

### 搜索技巧

1. **精确搜索**
   ```
   "书名"  # 使用引号进行精确匹配
   ```

2. **多关键词**
   ```
   斗破 苍穹  # 空格分隔多个关键词
   ```

3. **排除关键词**
   ```
   斗破 -同人  # 排除同人作品
   ```

### 搜索结果说明

| 字段 | 说明 |
|------|------|
| 📖 封面 | 书籍封面图片（如果有） |
| 📝 书名 | 完整书名 |
| ✍️ 作者 | 作者名称 |
| 📊 状态 | 完结/连载中 |
| 📚 字数 | 总字数 |
| 🏷️ 标签 | 类型标签 |
| ⬇️ 操作 | 下载、查看详情等操作 |

## ⬇️ 下载功能

### 下载选项

#### 格式选择
- **TXT**: 纯文本格式，体积小，兼容性好
- **EPUB**: 电子书格式，支持目录、样式，推荐阅读器使用

#### 章节范围
- **全部章节**: 下载整本书
- **自定义范围**: 指定起始和结束章节
- **最新章节**: 只下载最新发布的章节

#### 保存设置
- **保存路径**: 自定义下载文件保存位置
- **文件命名**: 自定义文件名格式
- **封面图片**: 是否下载并保存封面

### 下载流程

1. **选择书籍** → 2. **配置选项** → 3. **开始下载** → 4. **查看进度** → 5. **完成下载**

### 下载管理

#### 队列管理
- **添加到队列**: 选择书籍后点击下载
- **暂停下载**: 暂停当前下载任务
- **取消下载**: 取消未完成或正在下载的任务
- **重新下载**: 重新下载失败的任务

#### 并发控制
- **并发数量**: 同时下载的书籍数量（1-5）
- **章节并发**: 单本书籍的章节并发下载
- **速度限制**: 限制下载速度，避免对服务器造成压力

## 📄 格式说明

### TXT 格式

**特点**:
- 纯文本，体积小
- 兼容所有设备
- 无格式，适合纯阅读

**文件结构**:
```
[书名].txt
├── 书籍信息
├── 目录
└── 正文内容
    ├── 第一章 章节名
    ├── 第二章 章节名
    └── ...
```

**示例**:
```
《斗破苍穹》
作者：天蚕土豆
状态：完结

目录
第一章 陨落的天才
第二章 云岚宗
...

正文
第一章 陨落的天才
"斗之力，三段！"
...
```

### EPUB 格式

**特点**:
- 标准电子书格式
- 支持目录、样式
- 适配各种阅读器
- 包含封面图片

**文件结构**:
```
[书名].epub
├── META-INF/
├── OEBPS/
│   ├── Text/
│   │   ├── 目录.xhtml
│   │   ├── 第一章.xhtml
│   │   └── ...
│   ├── Styles/
│   │   └── style.css
│   ├── Images/
│   │   └── cover.jpg
│   └── content.opf
└── mimetype
```

**支持的阅读器**:
- 📱 手机：iBooks、Google Play 图书、微信读书
- 💻 电脑：Calibre、Adobe Digital Editions
- 📖 电纸书：Kindle（需转换）、Kobo、BOOX

## ⚙️ 高级功能

### 批量操作

#### 批量下载
1. 在搜索结果中勾选多本书籍
2. 点击"批量下载"按钮
3. 统一设置下载选项
4. 开始批量下载

#### 批量导出
- 将下载的书籍批量导出到指定位置
- 支持按作者、类型分类导出
- 可生成下载清单

### 自定义设置

#### 下载设置
```json
{
  "download": {
    "default_format": "epub",
    "default_path": "./novels",
    "concurrent_limit": 3,
    "timeout": 30,
    "retry_times": 3,
    "chapter_interval": 1,
    "save_cover": true,
    "create_folder": true
  }
}
```

#### 界面设置
```json
{
  "ui": {
    "theme": "light",
    "language": "zh-CN",
    "page_size": 20,
    "auto_refresh": true,
    "show_progress": true
  }
}
```

#### 网络设置
```json
{
  "network": {
    "proxy": null,
    "user_agent": "TomatoNovelDownloader/1.0",
    "connect_timeout": 10,
    "read_timeout": 30,
    "max_retries": 3
  }
}
```

### 插件系统

#### 自定义插件
创建自定义插件扩展功能：

```python
# plugins/custom_plugin.py
class CustomPlugin:
    def __init__(self):
        self.name = "Custom Plugin"
        self.version = "1.0.0"
    
    def on_download_start(self, book_info):
        print(f"开始下载: {book_info['title']}")
    
    def on_download_complete(self, book_info, file_path):
        print(f"下载完成: {file_path}")
    
    def on_error(self, error):
        print(f"下载错误: {error}")
```

## 💻 命令行详解

### 基本命令结构

```bash
python core/cli.py <command> [options] [arguments]
```

### 命令列表

#### search - 搜索书籍
```bash
# 基本搜索
python core/cli.py search "斗破苍穹"

# 按作者搜索
python core/cli.py search --author "天蚕土豆"

# 限制结果数量
python core/cli.py search "玄幻" --limit 10

# 输出为 JSON 格式
python core/cli.py search "斗破苍穹" --format json
```

#### info - 查看书籍信息
```bash
# 查看基本信息
python core/cli.py info 7372503659137005093

# 查看详细信息
python core/cli.py info 7372503659137005093 --detailed

# 查看章节列表
python core/cli.py info 7372503659137005093 --chapters
```

#### download - 下载单本书籍
```bash
# 基本下载
python core/cli.py download 7372503659137005093

# 指定格式
python core/cli.py download 7372503659137005093 --format epub

# 指定保存路径
python core/cli.py download 7372503659137005093 --path ~/Downloads

# 下载指定章节范围
python core/cli.py download 7372503659137005093 --chapter-start 1 --chapter-end 50

# 启用详细输出
python core/cli.py download 7372503659137005093 --verbose
```

#### batch-download - 批量下载
```bash
# 批量下载多本书
python core/cli.py batch-download 7372503659137005093 7372528691033300280

# 从文件读取书籍ID
python core/cli.py batch-download --input-file book_list.txt

# 设置并发数
python core/cli.py batch-download 7372503659137005093 7372528691033300280 --concurrent 3

# 设置全局选项
python core/cli.py batch-download 7372503659137005093 7372528691033300280 \
  --format epub \
  --path ~/novels \
  --concurrent 2 \
  --verbose
```

#### config - 配置管理
```bash
# 查看当前配置
python core/cli.py config --show

# 设置配置项
python core/cli.py config --set default_format=epub
python core/cli.py config --set concurrent_limit=3

# 重置配置
python core/cli.py config --reset

# 导出配置
python core/cli.py config --export config.json

# 导入配置
python core/cli.py config --import config.json
```

### 全局选项

| 选项 | 说明 | 示例 |
|------|------|------|
| `--help` | 显示帮助信息 | `--help` |
| `--version` | 显示版本信息 | `--version` |
| `--verbose` | 启用详细输出 | `--verbose` |
| `--quiet` | 静默模式 | `--quiet` |
| `--config` | 指定配置文件 | `--config custom.json` |
| `--proxy` | 设置代理 | `--proxy http://127.0.0.1:8080` |

## 🔧 配置管理

### 配置文件位置

- **Windows**: `%APPDATA%/TomatoNovelDownloader/config.json`
- **macOS**: `~/Library/Application Support/TomatoNovelDownloader/config.json`
- **Linux**: `~/.config/TomatoNovelDownloader/config.json`

### 配置文件模板

```json
{
  "version": "1.0.0",
  "download": {
    "default_format": "epub",
    "default_path": "./novels",
    "concurrent_limit": 3,
    "timeout": 30,
    "retry_times": 3,
    "chapter_interval": 1,
    "save_cover": true,
    "create_folder": true,
    "file_name_template": "{title}_{author}"
  },
  "ui": {
    "theme": "light",
    "language": "zh-CN",
    "page_size": 20,
    "auto_refresh": true,
    "show_progress": true,
    "refresh_interval": 5
  },
  "network": {
    "proxy": null,
    "user_agent": "TomatoNovelDownloader/1.0",
    "connect_timeout": 10,
    "read_timeout": 30,
    "max_retries": 3,
    "retry_delay": 1
  },
  "advanced": {
    "enable_plugins": true,
    "plugin_directory": "./plugins",
    "log_level": "INFO",
    "log_file": "./logs/app.log",
    "max_log_size": "10MB",
    "backup_config": true
  }
}
```

### 环境变量配置

```bash
# 下载相关
export TOMATO_DEFAULT_FORMAT=epub
export TOMATO_DOWNLOAD_PATH=~/novels
export TOMATO_CONCURRENT_LIMIT=3

# 网络相关
export HTTP_PROXY=http://127.0.0.1:8080
export HTTPS_PROXY=http://127.0.0.1:8080
export TOMATO_USER_AGENT="CustomUserAgent/1.0"

# 界面相关
export TOMATO_THEME=dark
export TOMATO_LANGUAGE=en-US
```

## ❓ 常见问题

### 下载问题

<details>
<summary><b>Q: 下载速度很慢怎么办？</b></summary>

**解决方案**：
1. 检查网络连接质量
2. 减少并发下载数量
3. 尝试在不同时间段下载
4. 检查是否设置了代理
5. 使用 CLI 模式通常更快
</details>

<details>
<summary><b>Q: 下载失败，提示"网络错误"</b></summary>

**解决方案**：
1. 检查网络连接
2. 尝试使用代理
3. 增加重试次数
4. 检查防火墙设置
5. 更换 DNS 服务器
</details>

<details>
<summary><b>Q: 下载的文件不完整或损坏</b></summary>

**解决方案**：
1. 重新下载文件
2. 检查磁盘空间是否充足
3. 关闭杀毒软件重试
4. 使用不同的格式下载
5. 检查书籍是否已被下架
</details>

### 格式问题

<details>
<summary><b>Q: EPUB 文件无法打开</b></summary>

**解决方案**：
1. 确保使用支持 EPUB 的阅读器
2. 尝试用不同的阅读器打开
3. 检查文件是否完整下载
4. 尝试转换为其他格式
5. 重新下载 EPUB 版本
</details>

<details>
<summary><b>Q: TXT 文件乱码</b></summary>

**解决方案**：
1. 确保使用 UTF-8 编码打开
2. 尝试用不同的文本编辑器
3. 转换文件编码为 GBK
4. 检查系统语言设置
5. 下载 EPUB 格式替代
</details>

### 界面问题

<details>
<summary><b>Q: Web 界面无法打开</b></summary>

**解决方案**：
1. 检查程序是否正常启动
2. 尝试访问 `http://localhost:5000`
3. 检查端口是否被占用
4. 重启程序
5. 检查防火墙设置
</details>

<details>
<summary><b>Q: 搜索无结果</b></summary>

**解决方案**：
1. 检查搜索关键词是否正确
2. 尝试使用更简单的关键词
3. 检查网络连接
4. 确认书籍是否存在于平台
5. 尝试按作者名搜索
</details>

### 性能问题

<details>
<summary><b>Q: 程序占用内存过高</b></summary>

**解决方案**：
1. 减少并发下载数量
2. 分批下载大量书籍
3. 关闭其他占用内存的程序
4. 重启程序释放内存
5. 使用 CLI 模式
</details>

<details>
<summary><b>Q: 程序响应缓慢</b></summary>

**解决方案**：
1. 检查系统资源使用情况
2. 清理下载缓存
3. 重启程序
4. 更新到最新版本
5. 使用更轻量的模式
</details>

## 📞 获取帮助

如果以上解决方案无法解决您的问题：

1. **查看日志**: 检查程序日志文件
2. **搜索 Issues**: 在 [GitHub Issues](https://github.com/POf-L/Fanqie-novel-Downloader/issues) 搜索类似问题
3. **提交新 Issue**: 创建新的 Issue，包含：
   - 详细的错误描述
   - 操作步骤
   - 系统环境信息
   - 错误日志
4. **联系作者**: 通过其他方式联系项目维护者

---

📖 **返回主文档**: [README.md](../README.md)
