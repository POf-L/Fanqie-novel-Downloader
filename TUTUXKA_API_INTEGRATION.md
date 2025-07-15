# Tutuxka API 集成文档

## 概述

本项目已成功集成了 Tutuxka API (https://qwq.tutuxka.top/)，为番茄小说下载器提供了更多的数据源选择。

## 功能特性

### 1. 支持的API功能

- ✅ **章节内容获取**: 单个章节内容下载
- ✅ **批量章节下载**: 多个章节同时下载
- ✅ **漫画内容获取**: 获取漫画图片URL或直接显示
- ✅ **听书功能**: 获取听书相关内容
- ✅ **书籍详情**: 获取书籍的详细信息
- ✅ **书籍评论**: 获取书籍的用户评论

### 2. API端点

基础URL: `https://qwq.tutuxka.top/api/index.php`

#### 支持的接口：

| 功能 | 参数 | 示例 |
|------|------|------|
| 章节内容 | `api=content&item_ids=章节ID` | `?api=content&item_ids=7276663560427471412` |
| 批量章节 | `api=content&item_ids=ID1,ID2&api_type=batch` | `?api=content&item_ids=123,456&api_type=batch` |
| 漫画内容 | `api=manga&item_ids=章节ID` | `?api=manga&item_ids=7276663560427471412` |
| 听书功能 | `api=content&ts=听书&item_ids=章节ID` | `?api=content&ts=听书&item_ids=7276663560427471412` |
| 书籍详情 | `api=content&book_id=书籍ID` | `?api=content&book_id=7237397843521047567` |
| 书籍评论 | `api=content&book_id=书籍ID&comment=评论` | `?api=content&book_id=123&comment=评论&count=10` |

## 代码集成

### 1. 配置

新API的配置在 `downloader.py` 中的 `CONFIG` 变量：

```python
"tutuxka_api": {
    "enabled": True,
    "base_url": "https://qwq.tutuxka.top/api/index.php",
    "priority": 1,
    "name": "tutuxka",
    "supports_batch": True,
    "supports_manga": True,
    "supports_audiobook": True,
    "supports_book_detail": True,
    "supports_comment": True
}
```

### 2. 主要函数

#### 核心API函数：

- `tutuxka_api_request(api_type, **kwargs)` - 统一API请求函数
- `tutuxka_get_chapter_content(chapter_id)` - 获取单章节内容
- `tutuxka_get_batch_chapters(chapter_ids)` - 批量获取章节
- `tutuxka_get_manga_content(chapter_id, show_html=False)` - 获取漫画内容
- `tutuxka_get_audiobook_content(chapter_id)` - 获取听书内容
- `tutuxka_get_book_detail(book_id)` - 获取书籍详情
- `tutuxka_get_book_comments(book_id, count=10, offset=0)` - 获取书籍评论

### 3. 集成到现有流程

API已集成到现有的下载流程中：

1. **章节下载**: `down_text()` 函数现在优先使用Tutuxka API
2. **批量下载**: `batch_download_chapters()` 函数支持Tutuxka API批量下载
3. **书籍信息**: `get_enhanced_book_info()` 函数集成了Tutuxka API的书籍详情功能

## 使用示例

### 基本使用

```python
from downloader import tutuxka_get_chapter_content

# 获取单个章节内容
title, content = tutuxka_get_chapter_content("7276663560427471412")
if title and content:
    print(f"章节标题: {title}")
    print(f"内容: {content}")
```

### 批量下载

```python
from downloader import tutuxka_get_batch_chapters

# 批量获取章节
chapter_ids = ["7276663560427471412", "7341402209906606616"]
batch_result = tutuxka_get_batch_chapters(chapter_ids)
```

### 获取书籍详情

```python
from downloader import tutuxka_get_book_detail

# 获取书籍详情
book_detail = tutuxka_get_book_detail("7237397843521047567")
```

## 测试

项目包含了完整的测试脚本：

- `test_tutuxka_api.py` - 完整的API功能测试
- `debug_tutuxka.py` - 调试单个API功能
- `tutuxka_api_example.py` - 使用示例

运行测试：
```bash
python test_tutuxka_api.py
```

## 故障转移机制

新API集成了完善的故障转移机制：

1. **优先级系统**: Tutuxka API设置为最高优先级
2. **自动回退**: 如果Tutuxka API不可用，自动回退到原有API
3. **错误处理**: 完善的异常处理和错误日志

## 配置选项

可以通过修改 `CONFIG["tutuxka_api"]` 来调整API行为：

- `enabled`: 是否启用API
- `priority`: 优先级（数字越小优先级越高）
- `supports_*`: 各功能开关

## 注意事项

1. **网络连接**: 确保能够访问 `https://qwq.tutuxka.top/`
2. **API限制**: 遵循API的使用限制和服务条款
3. **错误处理**: 程序包含完善的错误处理机制
4. **数据格式**: API返回的数据格式可能与原有API不同，已做适配处理

## 扩展功能

新API相比原有API新增了以下功能：

- 🆕 **漫画支持**: 可以获取漫画图片URL
- 🆕 **听书功能**: 支持听书相关内容
- 🆕 **书籍评论**: 可以获取用户评论
- 🆕 **详细书籍信息**: 更丰富的书籍元数据

## 维护和更新

- API接口稳定，无需频繁更新
- 如有问题，可以通过设置 `CONFIG["tutuxka_api"]["enabled"] = False` 临时禁用
- 建议定期检查API的可用性和响应速度