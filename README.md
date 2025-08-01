# Tomato Novel Downloader

基于参考代码修复的番茄小说下载器，支持GUI界面和命令行使用。

## 🚀 主要修复内容

### 1. API处理逻辑修复
- 修复了 `enhanced_downloader.py` 中 `down_text` 方法的API处理bug
- 修复了 `tomato_novel_api.py` 中的API调用逻辑
- 按照参考代码正确实现了所有API类型（fanqie_sdk, fqweb, qyuing, lsjk）的处理

### 2. 线程安全改进
- 添加了全局线程锁 `print_lock` 确保日志输出的线程安全
- 所有print语句都使用线程安全的方式输出

### 3. 错误处理优化
- 改善了API切换逻辑
- 添加了完整的异常处理机制
- 支持程序中断时的状态保存

### 4. 功能增强
- 保持了原有的GUI进度回调功能
- 添加了完整的命令行交互界面
- 支持章节范围选择下载
- 改进了EPUB格式的封面处理

## 📁 文件结构

- `enhanced_downloader.py` - 增强型下载器，支持GUI回调
- `tomato_novel_api.py` - API调用模块，包含完整的下载功能
- `gui.py` - 图形用户界面
- `updater.py` - 自动更新模块
- `version.py` - 版本信息

## 🛠️ 使用方法

### 命令行使用
```bash
# 直接运行增强下载器
python enhanced_downloader.py

# 测试API功能
python tomato_novel_api.py test

# 使用API模块
python tomato_novel_api.py search "小说名"
python tomato_novel_api.py novel_info "书籍ID"
```

### GUI使用
```bash
python gui.py
```

## 🔧 主要改进

1. **修复了关键bug**：
   - qyuing API的内容获取逻辑
   - lsjk API的响应处理
   - 批量下载的数据处理

2. **线程安全**：
   - 所有日志输出都使用线程锁保护
   - 避免了多线程环境下的输出混乱

3. **错误处理**：
   - 更完善的异常捕获和处理
   - 程序中断时的状态保存
   - API失败时的自动切换

4. **用户体验**：
   - 完整的命令行交互界面
   - 实时进度显示
   - 支持章节范围选择

## 📋 依赖要求

```
requests
bs4
fake_useragent
tqdm
ebooklib
PIL
urllib3
```

## 🎯 测试

运行测试命令验证修复效果：
```bash
python tomato_novel_api.py test
```

## 📝 更新日志

- 修复了API处理逻辑的关键bug
- 添加了线程安全机制
- 改善了错误处理和用户体验
- 保持了原有GUI功能的完整性