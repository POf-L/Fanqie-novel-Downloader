# 🤝 贡献指南

感谢您对番茄小说下载器项目的关注！我们欢迎所有形式的贡献。

## 📋 目录

- [贡献方式](#贡献方式)
- [开发环境搭建](#开发环境搭建)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [问题报告](#问题报告)
- [功能请求](#功能请求)
- [代码审查](#代码审查)
- [发布流程](#发布流程)

## 🎯 贡献方式

### 🐛 报告 Bug

发现 Bug？请帮助我们修复！

1. **检查现有 Issues**: 确保问题未被报告
2. **创建新 Issue**: 使用 Bug 报告模板
3. **提供详细信息**: 包含复现步骤、环境信息
4. **添加标签**: 选择合适的标签分类

### 💡 提出新功能

有好想法？我们想听听！

1. **检查现有请求**: 确保功能未被提议
2. **创建功能请求**: 使用功能请求模板
3. **详细描述**: 说明功能用途和实现思路
4. **讨论可行性**: 与维护者讨论实现方案

### 📝 改进文档

文档同样重要！

1. **发现错误**: 找出文档中的错误或不足
2. **提出改进**: 建议更好的表达方式
3. **补充内容**: 添加缺失的使用说明
4. **翻译文档**: 帮助翻译成其他语言

### 🔧 提交代码

直接贡献代码！

1. **Fork 项目**: 创建您的项目副本
2. **创建分支**: 为您的功能创建独立分支
3. **编写代码**: 遵循项目代码规范
4. **测试验证**: 确保代码正常工作
5. **提交 PR**: 创建 Pull Request

### 🌟 推广项目

帮助更多人了解项目！

1. **分享给朋友**: 推荐给需要的人
2. **写教程**: 制作使用教程或视频
3. **社交媒体**: 在社交平台分享
4. **写评价**: 在相关平台写评价

## 🛠️ 开发环境搭建

### 系统要求

- **Python**: 3.7+ (推荐 3.9+)
- **Git**: 最新版本
- **IDE**: VS Code, PyCharm 或其他
- **操作系统**: Windows 10+, macOS 10.14+, Ubuntu 18.04+

### 克隆项目

```bash
# 克隆您的 Fork
git clone https://github.com/YOUR_USERNAME/Fanqie-novel-Downloader.git
cd Fanqie-novel-Downloader

# 添加上游仓库
git remote add upstream https://github.com/POf-L/Fanqie-novel-Downloader.git
```

### 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 安装依赖

```bash
# 安装基础依赖
pip install -r config/requirements.txt

# 安装开发依赖
pip install -r config/requirements-dev.txt

# 安装 pre-commit hooks
pre-commit install
```

### 配置开发环境

```bash
# 复制配置文件
cp config/config.example.json config/config.json

# 设置环境变量
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export FLASK_ENV=development
export FLASK_DEBUG=1
```

### 运行项目

```bash
# 运行主程序
python main.py

# 运行测试
pytest tests/

# 运行代码检查
flake8 .
black .
mypy .
```

## 📝 代码规范

### Python 代码风格

我们使用以下工具确保代码质量：

- **Black**: 代码格式化
- **Flake8**: 代码检查
- **isort**: 导入排序
- **mypy**: 类型检查

#### 基本规范

```python
# 好的示例
import os
import sys
from typing import Optional, List

from config.config import CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class NovelDownloader:
    """小说下载器类"""
    
    def __init__(self, config: dict) -> None:
        self.config = config
        self.session = None
    
    def download_novel(
        self, 
        book_id: str, 
        format: str = "txt"
    ) -> Optional[str]:
        """
        下载小说
        
        Args:
            book_id: 书籍ID
            format: 下载格式
            
        Returns:
            下载文件路径，失败返回 None
        """
        try:
            # 实现下载逻辑
            logger.info(f"开始下载小说: {book_id}")
            # ...
            return file_path
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return None
```

#### 命名规范

- **变量和函数**: `snake_case`
- **类名**: `PascalCase`
- **常量**: `UPPER_SNAKE_CASE`
- **私有成员**: 前缀 `_`

#### 文档字符串

```python
def process_chapter_content(
    content: str, 
    chapter_id: int,
    options: dict = None
) -> str:
    """
    处理章节内容
    
    Args:
        content: 原始章节内容
        chapter_id: 章节ID
        options: 处理选项，可选
        
    Returns:
        处理后的内容
        
    Raises:
        ValueError: 当内容格式不正确时
        
    Example:
        >>> content = "第一章 内容..."
        >>> result = process_chapter_content(content, 1)
        >>> print(result)
        处理后的内容
    """
    pass
```

### JavaScript/HTML/CSS 规范

#### JavaScript

```javascript
// 好的示例
class DownloadManager {
    constructor() {
        this.queue = [];
        this.activeDownloads = 0;
        this.maxConcurrent = 3;
    }
    
    async downloadBook(bookId, format = 'txt') {
        try {
            if (this.activeDownloads >= this.maxConcurrent) {
                await this.waitForSlot();
            }
            
            this.activeDownloads++;
            const result = await this._performDownload(bookId, format);
            return result;
        } catch (error) {
            console.error(`下载失败: ${bookId}`, error);
            throw error;
        } finally {
            this.activeDownloads--;
        }
    }
}
```

#### HTML

```html
<!-- 好的示例 -->
<div class="search-container">
    <div class="search-input-group">
        <input 
            type="text" 
            id="searchInput" 
            class="form-control" 
            placeholder="输入书名或作者"
            autocomplete="off"
        >
        <button 
            type="button" 
            id="searchBtn" 
            class="btn btn-primary"
            aria-label="搜索"
        >
            <i class="fas fa-search"></i>
            搜索
        </button>
    </div>
    <div id="searchResults" class="search-results" role="region" aria-live="polite">
        <!-- 搜索结果将在这里显示 -->
    </div>
</div>
```

#### CSS

```css
/* 好的示例 */
.search-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 1rem;
}

.search-input-group {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.search-input-group input {
    flex: 1;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
}

.search-input-group input:focus {
    outline: none;
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
}
```

## 📋 提交规范

### Commit Message 格式

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### Type 类型

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式化（不影响功能）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

#### 示例

```bash
# 新功能
git commit -m "feat(download): 添加批量下载功能"

# Bug 修复
git commit -m "fix(web): 修复搜索结果分页问题"

# 文档更新
git commit -m "docs(readme): 更新安装说明"

# 代码重构
git commit -m "refactor(core): 重构下载器模块结构"
```

### 分支策略

#### 主要分支

- `main`: 主分支，稳定版本
- `develop`: 开发分支，最新功能
- `release/*`: 发布分支
- `hotfix/*`: 热修复分支

#### 功能分支

```bash
# 创建功能分支
git checkout -b feature/batch-download

# 创建修复分支
git checkout -b fix/search-pagination

# 创建文档分支
git checkout -b docs/api-guide
```

### Pull Request 流程

1. **创建分支**: 从 `develop` 创建功能分支
2. **开发功能**: 编写代码和测试
3. **提交代码**: 遵循提交规范
4. **推送分支**: 推送到您的 Fork
5. **创建 PR**: 向 `develop` 分支提交 PR
6. **代码审查**: 等待维护者审查
7. **合并代码**: 审查通过后合并

#### PR 模板

```markdown
## 变更描述
简要描述此 PR 的变更内容

## 变更类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 代码重构
- [ ] 文档更新
- [ ] 其他

## 测试
- [ ] 已添加新测试
- [ ] 所有测试通过
- [ ] 手动测试通过

## 检查清单
- [ ] 代码遵循项目规范
- [ ] 已更新相关文档
- [ ] 无明显性能问题
- [ ] 兼容性良好

## 相关 Issue
Closes #(issue number)

## 截图（如适用）
添加相关截图或 GIF

## 其他说明
其他需要说明的内容
```

## 🐛 问题报告

### Bug 报告模板

```markdown
**Bug 描述**
简要描述遇到的问题

**复现步骤**
1. 进入 '...'
2. 点击 '....'
3. 滚动到 '....'
4. 看到错误

**期望行为**
描述您期望发生的情况

**实际行为**
描述实际发生的情况

**截图**
如果适用，添加截图帮助解释问题

**环境信息**
- 操作系统: [例如 Windows 11]
- Python 版本: [例如 3.9.7]
- 程序版本: [例如 v1.2.0]
- 浏览器: [例如 Chrome 96.0]

**附加信息**
添加其他相关信息
```

### 如何有效报告 Bug

1. **搜索现有 Issues**: 确保问题未被报告
2. **使用模板**: 填写完整的 Bug 报告
3. **提供复现步骤**: 详细说明如何重现问题
4. **包含环境信息**: 操作系统、版本等
5. **添加日志**: 如果有错误日志，请附上
6. **保持简洁**: 避免冗余信息

## 💡 功能请求

### 功能请求模板

```markdown
**功能描述**
简要描述您希望添加的功能

**问题背景**
描述这个功能要解决的问题

**解决方案**
描述您希望的解决方案

**替代方案**
描述您考虑过的其他解决方案

**使用场景**
描述这个功能的使用场景

**附加信息**
添加其他相关信息或截图
```

### 如何提出好的功能请求

1. **检查现有请求**: 确保功能未被提议
2. **描述问题**: 清楚说明要解决的问题
3. **提供解决方案**: 给出具体的实现思路
4. **考虑影响**: 思考功能对现有代码的影响
5. **讨论优先级**: 与维护者讨论实现优先级

## 🔍 代码审查

### 审查要点

#### 功能性
- [ ] 功能是否按预期工作
- [ ] 是否有边界情况未处理
- [ ] 错误处理是否完善
- [ ] 性能是否可接受

#### 代码质量
- [ ] 代码是否清晰易懂
- [ ] 是否遵循项目规范
- [ ] 是否有重复代码
- [ ] 变量和函数命名是否合理

#### 测试
- [ ] 是否有足够的测试覆盖
- [ ] 测试用例是否合理
- [ ] 是否有集成测试
- [ ] 手动测试是否通过

#### 文档
- [ ] 是否更新了相关文档
- [ ] 代码注释是否充分
- [ ] API 文档是否准确
- [ ] 使用示例是否正确

### 审查流程

1. **自动检查**: CI/CD 自动运行测试和检查
2. **人工审查**: 维护者进行代码审查
3. **反馈修改**: 根据审查意见修改代码
4. **再次审查**: 修改后再次审查
5. **合并代码**: 审查通过后合并

## 🚀 发布流程

### 版本号规范

我们使用 [语义化版本](https://semver.org/lang/zh-CN/)：

- **主版本号**: 不兼容的 API 修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

### 发布步骤

1. **准备发布**
   ```bash
   # 更新版本号
   bump2version patch  # 或 minor, major
   
   # 更新 CHANGELOG
   # 更新文档中的版本号
   ```

2. **创建发布分支**
   ```bash
   git checkout -b release/v1.2.3
   ```

3. **最终测试**
   ```bash
   # 运行完整测试套件
   pytest tests/
   
   # 构建可执行文件
   python tools/build_app.py
   ```

4. **合并和标记**
   ```bash
   git checkout main
   git merge release/v1.2.3
   git tag v1.2.3
   ```

5. **发布**
   ```bash
   git push origin main --tags
   # GitHub Actions 会自动构建和发布
   ```

### 发布检查清单

- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] CHANGELOG 已更新
- [ ] 版本号已更新
- [ ] 构建成功
- [ ] 发布说明已准备

## 🏆 贡献者认可

### 贡献者列表

所有贡献者都会在项目中得到认可：

- **README**: 添加贡献者列表
- **CHANGELOG**: 在版本更新中感谢贡献者
- **Contributors**: GitHub 自动统计贡献

### 成为维护者

活跃的贡献者可以成为项目维护者：

1. **持续贡献**: 长期高质量贡献
2. **代码审查**: 参与代码审查
3. **问题处理**: 帮助解决社区问题
4. **社区建设**: 帮助建设社区文化

## 📞 联系方式

如有任何问题或建议：

- **GitHub Issues**: [提交问题](https://github.com/POf-L/Fanqie-novel-Downloader/issues)
- **GitHub Discussions**: [参与讨论](https://github.com/POf-L/Fanqie-novel-Downloader/discussions)
- **Email**: [联系维护者](mailto:author@example.com)

## 📄 许可证

通过贡献代码，您同意您的贡献将在与项目相同的 [MIT 许可证](../LICENSE) 下授权。

---

感谢您的贡献！🎉

📖 **返回主文档**: [README.md](../README.md)
