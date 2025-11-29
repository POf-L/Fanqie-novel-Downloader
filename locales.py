# -*- coding: utf-8 -*-
"""
Language Configuration / 语言配置文件
"""

# Default language
# 可以通过修改此变量切换语言 / Change this to 'en' to switch language
DEFAULT_LANG = "zh"

# Translations
MESSAGES = {
    "zh": {
        # config.py
        "config_fetching": "正在获取最新的 API 配置: {}",
        "config_success": "成功加载配置，API 地址: {}",
        "config_fail": "获取远程配置失败: {}",
        "config_server_error": "⚠️ 警告: 无法连接配置服务器，程序可能无法正常工作",
        
        # main.py
        "main_app_closed": "应用已关闭",
        "main_webview_init_fail": "PyWebView 浏览器引擎初始化失败: {}",
        "main_switch_browser": "自动切换到系统浏览器...",
        "main_webview_fail": "PyWebView 启动失败: {}",
        "main_webview_unavailable": "PyWebView 未安装或不可用，使用系统浏览器打开...",
        "main_interface_fail": "打开界面失败: {}",
        "main_title": "番茄小说下载器 - Web 版",
        "main_version": "当前版本: {}",
        "main_config_path": "配置文件: {}",
        "main_webview2_config": "正在配置内置 WebView2: {}",
        "main_check_deps": "检查依赖...",
        "main_missing_deps": "缺少依赖: {}",
        "main_install_deps": "请运行: pip install flask flask-cors",
        "main_starting": "启动应用...",
        "main_wait_server": "等待服务器启动...",
        "main_server_started": "✓ 服务器已启动",
        "main_server_timeout": "✗ 服务器启动超时",
        "main_opening_interface": "打开应用界面...",
        "main_flask_fail": "Flask 应用启动失败: {}",
        
        # web_app.py
        "web_update_check": "正在检查更新...",
        "web_update_status_dl": "正在下载: {}%",
        "web_update_status_connect": "正在连接服务器...",
        "web_update_status_start": "开始下载...",
        "web_update_complete": "下载完成，点击\"应用更新\"安装",
        "web_update_cancelled": "下载被取消",
        "web_update_fail": "下载失败: {}",
        "web_search_keyword_empty": "请输入搜索关键词",
        "web_api_not_init": "API未初始化",
        "web_search_fail": "搜索失败: {}",
        "web_book_id_empty": "请输入书籍ID或URL",
        "web_url_error": "URL格式错误",
        "web_id_not_digit": "书籍ID应为纯数字",
        "web_book_info_fail": "获取书籍信息失败",
        "web_chapter_list_fail": "无法获取章节列表",
        "web_get_info_fail": "获取信息失败: {}",
        "web_download_exists": "已有下载任务在进行",
        "web_save_path_error": "保存路径错误: {}",
        "web_task_added": "任务已加入队列",
        "web_task_started": "下载任务已开始",
        "web_auto_update_unsupported": "当前环境不支持自动更新，请手动替换程序文件",
        "web_update_not_ready": "更新文件尚未下载完成",
        "web_update_info_incomplete": "更新文件信息不完整",
        "web_update_file_missing": "更新文件不存在: {}",
        "web_update_start_success": "更新程序已启动，应用即将关闭并自动更新...",
        "web_update_start_fail": "启动更新程序失败",
        "web_apply_update_fail": "应用更新失败: {}",
        "web_path_not_exist": "路径不存在",
        "web_server_started": "系统已启动，等待操作...",
        
        # novel_downloader.py
        "dl_search_error": "搜索异常: {}",
        "dl_detail_error": "获取书籍详情异常: {}",
        "dl_chapter_list_start": "[DEBUG] 开始获取章节列表: ID={}",
        "dl_chapter_list_resp": "[DEBUG] 章节列表响应: {}",
        "dl_chapter_list_error": "获取章节列表异常: {}",
        "dl_content_error": "获取章节内容异常: {}",
        "dl_save_status_fail": "保存下载状态失败: {}",
        "dl_cover_fail": "下载封面失败: {}",
        "dl_cover_add_fail": "添加封面失败: {}",
        "dl_search_fail": "搜索失败: {}",
        "dl_batch_no_books": "没有要下载的书籍",
        "dl_batch_api_fail": "API 初始化失败",
        "dl_batch_start": "📚 开始批量下载，共 {} 本书籍",
        "dl_batch_cancelled": "⚠️ 批量下载已取消",
        "dl_batch_downloading": "[{}/{}] 开始下载: 《{}》",
        "dl_batch_progress": "正在下载第 {} 本...",
        "dl_batch_success": "✅ 《{}》下载完成",
        "dl_batch_fail": "❌ 《{}》下载失败",
        "dl_batch_exception": "❌ 《{}》下载异常: {}",
        "dl_batch_summary": "📊 批量下载完成统计:",
        "dl_batch_stats_success": "   成功: {} 本",
        "dl_batch_stats_fail": "   失败: {} 本",
        "dl_batch_stats_total": "   总计: {} 本",
        "dl_batch_fail_list": "❌ 失败列表:",
        "dl_batch_complete": "完成 {}/{} 本",
        "dl_chapter_title": "第{}章",
        "dl_unknown_book": "未知书名",
        "dl_unknown_author": "未知作者",
        "dl_no_intro": "暂无简介",
        "dl_status_finished": "已完结",
        "dl_status_serializing": "连载中",
        "dl_status_completed_2": "完结",
        
        # updater.py
        "up_check_fail": "⚠️ 无法检查更新，请检查网络连接",
        "up_latest": "✅ 当前已是最新版本 ({})",
        "up_not_frozen": "自动更新仅支持打包后的程序",
        "up_new_missing": "新版本文件不存在: {}",
        "up_desc_standalone": "完整版 - 内置 WebView2 运行时,开箱即用",
        "up_desc_debug": "调试版 - 包含调试信息和控制台窗口",
        "up_desc_standard": "标准版 - 需要系统已安装 WebView2",
        "up_desc_linux_debug": "调试版",
        "up_desc_linux_release": "发布版",
        
        # watermark.py
        "wm_watermark_full": "当前小说使用https://github.com/POf-L/Fanqie-novel-Downloader免费下载器下载，购买的请立即差评并申请退款和举报！",
        "wm_watermark_simple": "当前小说使用https://github.com/POf-L/Fanqie-novel-Downloader下载",
    },
    "en": {
         # config.py
        "config_fetching": "Fetching latest API config: {}",
        "config_success": "Config loaded, API base URL: {}",
        "config_fail": "Failed to fetch remote config: {}",
        "config_server_error": "⚠️ Warning: Cannot connect to config server, app may not work properly",
        
        # main.py
        "main_app_closed": "Application closed",
        "main_webview_init_fail": "PyWebView engine init failed: {}",
        "main_switch_browser": "Switching to system browser...",
        "main_webview_fail": "PyWebView failed to start: {}",
        "main_webview_unavailable": "PyWebView unavailable, opening in system browser...",
        "main_interface_fail": "Failed to open interface: {}",
        "main_title": "Tomato Novel Downloader - Web Edition",
        "main_version": "Current Version: {}",
        "main_config_path": "Config File: {}",
        "main_webview2_config": "Configuring built-in WebView2: {}",
        "main_check_deps": "Checking dependencies...",
        "main_missing_deps": "Missing dependencies: {}",
        "main_install_deps": "Please run: pip install flask flask-cors",
        "main_starting": "Starting application...",
        "main_wait_server": "Waiting for server to start...",
        "main_server_started": "✓ Server started",
        "main_server_timeout": "✗ Server start timeout",
        "main_opening_interface": "Opening application interface...",
        "main_flask_fail": "Flask app failed to start: {}",
        
        # web_app.py
        "web_update_check": "Checking for updates...",
        "web_update_status_dl": "Downloading: {}%",
        "web_update_status_connect": "Connecting to server...",
        "web_update_status_start": "Starting download...",
        "web_update_complete": "Download complete, click 'Apply Update'",
        "web_update_cancelled": "Download cancelled",
        "web_update_fail": "Download failed: {}",
        "web_search_keyword_empty": "Please enter search keyword",
        "web_api_not_init": "API not initialized",
        "web_search_fail": "Search failed: {}",
        "web_book_id_empty": "Please enter Book ID or URL",
        "web_url_error": "Invalid URL format",
        "web_id_not_digit": "Book ID must be digits",
        "web_book_info_fail": "Failed to get book info",
        "web_chapter_list_fail": "Failed to get chapter list",
        "web_get_info_fail": "Failed to get info: {}",
        "web_download_exists": "A download task is already running",
        "web_save_path_error": "Invalid save path: {}",
        "web_task_added": "Task added to queue",
        "web_task_started": "Download task started",
        "web_auto_update_unsupported": "Auto-update not supported in this environment",
        "web_update_not_ready": "Update file not fully downloaded",
        "web_update_info_incomplete": "Update info incomplete",
        "web_update_file_missing": "Update file missing: {}",
        "web_update_start_success": "Update started, app will close...",
        "web_update_start_fail": "Failed to start updater",
        "web_apply_update_fail": "Apply update failed: {}",
        "web_path_not_exist": "Path does not exist",
        "web_server_started": "System initialized, waiting for input...",
        
        # novel_downloader.py
        "dl_search_error": "Search error: {}",
        "dl_detail_error": "Get book detail error: {}",
        "dl_chapter_list_start": "[DEBUG] Start fetching chapters: ID={}",
        "dl_chapter_list_resp": "[DEBUG] Chapter list response: {}",
        "dl_chapter_list_error": "Get chapter list error: {}",
        "dl_content_error": "Get chapter content error: {}",
        "dl_save_status_fail": "Save status failed: {}",
        "dl_cover_fail": "Download cover failed: {}",
        "dl_cover_add_fail": "Add cover failed: {}",
        "dl_search_fail": "Search failed: {}",
        "dl_batch_no_books": "No books to download",
        "dl_batch_api_fail": "API initialization failed",
        "dl_batch_start": "📚 Batch download started, {} books total",
        "dl_batch_cancelled": "⚠️ Batch download cancelled",
        "dl_batch_downloading": "[{}/{}] Downloading: 《{}》",
        "dl_batch_progress": "Downloading book {} ...",
        "dl_batch_success": "✅ 《{}》 Downloaded",
        "dl_batch_fail": "❌ 《{}》 Failed",
        "dl_batch_exception": "❌ 《{}》 Exception: {}",
        "dl_batch_summary": "📊 Batch Download Summary:",
        "dl_batch_stats_success": "   Success: {}",
        "dl_batch_stats_fail": "   Failed: {}",
        "dl_batch_stats_total": "   Total: {}",
        "dl_batch_fail_list": "❌ Failed List:",
        "dl_batch_complete": "Completed {}/{}",
        "dl_chapter_title": "Chapter {}",
        "dl_unknown_book": "Unknown Title",
        "dl_unknown_author": "Unknown Author",
        "dl_no_intro": "No description",
        "dl_status_finished": "Finished",
        "dl_status_serializing": "Ongoing",
        "dl_status_completed_2": "Completed",
        
        # updater.py
        "up_check_fail": "⚠️ Update check failed, check network",
        "up_latest": "✅ Already latest version ({})",
        "up_not_frozen": "Auto-update only for frozen app",
        "up_new_missing": "New version file missing: {}",
        "up_desc_standalone": "Standalone - Built-in WebView2 Runtime",
        "up_desc_debug": "Debug - With console window",
        "up_desc_standard": "Standard - Requires system WebView2",
        "up_desc_linux_debug": "Debug",
        "up_desc_linux_release": "Release",
        
        # watermark.py
        "wm_watermark_full": "This novel is downloaded using https://github.com/POf-L/Fanqie-novel-Downloader. If you paid for this, please report and refund immediately!",
        "wm_watermark_simple": "Downloaded using https://github.com/POf-L/Fanqie-novel-Downloader",
    }
}

def t(key, *args):
    """
    Get translated string
    Args:
        key: Message key
        *args: Format arguments
    """
    lang_code = DEFAULT_LANG
    # Fallback to zh if lang not found
    if lang_code not in MESSAGES:
        lang_code = "zh"
        
    lang_dict = MESSAGES.get(lang_code, {})
    
    # If key not in current lang, try zh
    if key not in lang_dict:
        msg = MESSAGES.get("zh", {}).get(key, key)
    else:
        msg = lang_dict[key]
        
    if args:
        try:
            return msg.format(*args)
        except Exception:
            return msg
    return msg
