# 番茄小说下载器

一个现代化、高效的番茄小说下载器，使用 Python 构建，配备简洁、响应式的网页界面。

## 功能特性

-   **图书搜索**: 轻松按标题或作者搜索图书。
-   **批量下载**: 一次下载多本图书。
-   **格式支持**: 导出为 **TXT**（纯文本）或 **EPUB**（电子书）格式。
-   **封面图片**: 自动获取并在 EPUB 文件中嵌入图书封面。
-   **章节选择**: 下载完整图书、特定范围或手动选择的章节。
-   **跨平台**: 支持 Windows、macOS、Linux 和 Termux（Android）。
-   **☁️ GitHub Actions 云端下载**: 无需本地环境，直接在 GitHub 云端批量下载小说。

## 安装与使用

### 方式一：GitHub Actions 云端下载 ☁️ (推荐)

**无需安装任何软件，直接在 GitHub 云端下载小说！**

#### 快速开始（3步）

1. **进入 Actions 页面**
   - 打开本仓库
   - 点击顶部的 **Actions** 标签
   - 选择左侧的 **Download Novels** 工作流

2. **触发下载**
   - 点击 **Run workflow** 按钮
   - 填写参数：
     ```
     书籍ID列表: 7372503659137005093, 7372528691033300280
     输出格式: txt 或 epub
     保存路径: downloads
     并发数量: 3
     ```
   - 点击绿色的 **Run workflow** 开始

3. **下载文件**
   - 等待执行完成（5-15分钟）
   - 进入运行详情页面
   - 在底部 **Artifacts** 区域下载压缩包

#### 主要特性

- 🚀 **云端执行**：无需本地安装 Python 环境
- 📦 **批量下载**：支持一次性下载多本小说
- 🔄 **并发控制**：可配置并发数量（1-5）
- 💾 **自动保存**：下载完成后自动打包为 Artifact
- 📊 **详细报告**：生成下载统计报告
- ⏰ **长期保存**：Artifact 保留 30 天

#### 参数说明

| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| **书籍ID列表** | 要下载的书籍ID（逗号或空格分隔） | `7372503659137005093, 7372528691033300280` |
| **输出格式** | `txt` 或 `epub` | `txt` |
| **保存路径** | 下载文件保存位置（可选） | `downloads` |
| **并发数量** | 同时下载的书籍数（1-5，可选） | `3` |

#### 如何获取书籍ID

**方法1：从网页URL获取**
```
URL: https://fanqienovel.com/page/7372503659137005093
书籍ID: 7372503659137005093
```

**方法2：使用搜索功能**
```bash
python core/cli.py search "斗破苍穹"
```

#### 使用示例

**示例 1：下载单本小说（TXT格式）**
```
书籍ID列表: 7372503659137005093
输出格式: txt
保存路径: downloads
并发数量: 1
```

**示例 2：批量下载多本小说（EPUB格式）**
```
书籍ID列表: 7372503659137005093, 7372528691033300280, 7123456789012345678
输出格式: epub
保存路径: novels/fantasy
并发数量: 3
```

**示例 3：大批量下载（高并发）**
```
书籍ID列表: 7372503659137005093, 7372528691033300280, 7123456789012345678, 7234567890123456789, 7345678901234567890
输出格式: txt
保存路径: downloads/batch-2024
并发数量: 5
```

#### 下载报告

每次下载完成后，会在 Actions 运行页面的 **Summary** 标签中生成详细报告，包含：

- **下载配置**：书籍数量、输出格式、并发数、保存路径
- **下载结果**：成功文件数量、总文件大小、Artifact 名称
- **下载指引**：如何获取下载的文件、Artifact 保留时间

#### 常见问题

<details>
<summary><b>Q: Artifact 在哪里下载？</b></summary>

进入 Actions 运行详情页 → 滚动到页面底部 → 在 **Artifacts** 区域找到压缩包
</details>

<details>
<summary><b>Q: Artifact 保留多久？</b></summary>

保留 30 天，建议及时下载到本地保存
</details>

<details>
<summary><b>Q: 可以下载多少本书？</b></summary>

理论上无限制，建议单次不超过 20 本，避免超时（Actions 单次运行最长 6 小时）
</details>

<details>
<summary><b>Q: 下载速度慢怎么办？</b></summary>

1. 增加并发数（最大5）
2. 分批下载
3. 选择 TXT 格式（比 EPUB 快）
</details>

<details>
<summary><b>Q: 下载失败怎么办？</b></summary>

1. 检查书籍ID是否正确
2. 查看 Actions 日志中的错误信息
3. 稍后重试
</details>

<details>
<summary><b>Q: 支持断点续传吗？</b></summary>

当前版本不支持。下载失败后重新运行，项目会自动跳过已存在的文件
</details>

<details>
<summary><b>Q: 可以定时自动下载吗？</b></summary>

当前版本仅支持手动触发。如需定时任务，可修改 `.github/workflows/download-novels.yml` 添加 `schedule` 触发器：

```yaml
on:
  workflow_dispatch:
    # ... 现有配置
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点执行
```
</details>

<details>
<summary><b>Q: 可以自动提交到仓库吗？</b></summary>

可以修改 workflow 添加自动提交步骤：

```yaml
- name: 提交下载的文件
  run: |
    git config user.name "GitHub Actions"
    git config user.email "actions@github.com"
    git add downloads/
    git commit -m "Auto download novels"
    git push
```
</details>

#### 工作流程

```
手动触发 (输入参数)
  ↓
检出代码
  ↓
设置 Python 环境
  ↓
安装依赖
  ↓
解析书籍ID列表
  ↓
执行批量下载 (并发)
  ↓
统计下载结果
  ↓
上传为 Artifact
  ↓
生成下载报告
  ↓
完成
```

#### 安全说明

- ✅ 工作流仅有 `contents: read` 权限
- ✅ 不会修改仓库内容（除非你自定义）
- ✅ 下载的文件仅保存在 Artifact 中
- ✅ 30天后自动删除

---

### 方式二：本地安装使用

#### Windows / macOS / Linux

1.  **下载**: 从 [发布页面](https://github.com/POf-L/Fanqie-novel-Downloader/releases) 获取最新版本。
2.  **运行**:
    -   **Windows**: 运行 `.exe` 文件。
    -   **Linux/macOS**: 授予执行权限（`chmod +x ...`）并运行二进制文件。

#### 源代码（Python）

要求: Python 3.7+

1.  克隆仓库:
    ```bash
    git clone https://github.com/POf-L/Fanqie-novel-Downloader.git
    cd Fanqie-novel-Downloader
    ```

2.  安装依赖:
    ```bash
    pip install -r config/requirements.txt
    ```

3.  运行程序:
    ```bash
    # GUI 模式
    python main.py

    # CLI 模式
    python core/cli.py --help
    ```

---

## 使用指南

### GUI 界面使用

1. 启动程序后会自动打开网页界面
2. 在搜索框输入书名或作者名
3. 选择要下载的书籍
4. 选择格式（TXT/EPUB）和章节范围
5. 点击下载按钮

### CLI 命令行使用

```bash
# 搜索书籍
python core/cli.py search "斗破苍穹"

# 查看书籍信息
python core/cli.py info 7372503659137005093

# 下载单本书籍
python core/cli.py download 7372503659137005093 --format txt

# 批量下载
python core/cli.py batch-download 7372503659137005093 7372528691033300280 --format epub --concurrent 3
```

---

## 更多信息

### 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 📄 许可证

本项目采用开源许可证，详见 LICENSE 文件。

### ⭐ 支持项目

如果这个项目对你有帮助，请给个 Star ⭐ 支持一下！

