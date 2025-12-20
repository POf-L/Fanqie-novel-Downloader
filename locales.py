# -*- coding: utf-8 -*-
"""
Language Configuration / 语言配置文件
"""

import os
import json
import tempfile

# Default language
# 可以通过修改此变量切换语言 / Change this to 'en' to switch language
DEFAULT_LANG = "zh"

# 配置文件路径（与 web_app.py 保持一致）
_CONFIG_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

def get_current_lang():
    """从配置文件读取当前语言设置"""
    try:
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('language', DEFAULT_LANG)
    except:
        pass
    return DEFAULT_LANG

def set_current_lang(lang):
    """保存语言设置到配置文件"""
    try:
        config = {}
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        config['language'] = lang
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

# Translations
MESSAGES = {
    "zh": {
        # config.py
        "config_loading_local": "正在加载本地配置...",
        "config_success": "成功加载配置，API 地址: {}",
        "config_fail": "获取远程配置失败: {}",
        "config_server_error": "警告: 无法连接配置服务器，程序可能无法正常工作",
        "config_invalid_format": "警告: 远程配置格式无效",
        "config_json_error": "警告: 远程配置 JSON 解析失败: {}",
        
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
        "main_server_started": "服务器已启动",
        "main_server_timeout": "服务器启动超时",
        "main_opening_interface": "打开应用界面...",
        "main_flask_fail": "Flask 应用启动失败: {}",
        
        # web_app.py
        "web_update_status_dl": "正在下载: {}%",
        "web_update_status_connect": "正在连接服务器...",
        "web_update_status_start": "开始下载...",
        "web_update_status_merging": "正在合并文件...",
        "web_update_connect_fail": "无法连接到下载服务器，请检查网络或代理设置",
        "web_update_complete": "下载完成，点击\"应用更新\"安装",
        "web_update_fail": "下载失败: {}",
        "web_search_keyword_empty": "请输入搜索关键词",
        "web_api_not_init": "API未初始化",
        "web_search_fail": "搜索失败: {}",
        "web_book_id_empty": "请输入书籍ID或URL",
        "web_url_error": "URL格式错误",
        "web_id_not_digit": "书籍ID应为纯数字",
        "web_book_info_fail": "获取书籍信息失败",
        "web_chapter_list_fail": "无法获取章节列表",
        "web_download_exists": "已有下载任务在进行",
        
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
        "dl_batch_start": "开始批量下载，共 {} 本书籍",
        "dl_batch_cancelled": "批量下载已取消",
        "dl_batch_downloading": "[{}/{}] 开始下载: 《{}》",
        "dl_batch_progress": "正在下载第 {} 本...",
        "dl_batch_success": "《{}》下载完成",
        "dl_batch_fail": "《{}》下载失败",
        "dl_batch_exception": "《{}》下载异常: {}",
        "dl_batch_summary": "批量下载完成统计:",
        "dl_batch_stats_success": "   成功: {} 本",
        "dl_batch_stats_fail": "   失败: {} 本",
        "dl_batch_stats_total": "   总计: {} 本",
        "dl_batch_fail_list": "失败列表:",
        "dl_batch_complete": "完成 {}/{} 本",
        "dl_chapter_title": "第{}章",
        "dl_unknown_book": "未知书名",
        "dl_unknown_author": "未知作者",
        "dl_no_intro": "暂无简介",
        "dl_status_finished": "已完结",
        "dl_status_serializing": "连载中",
        "dl_status_completed_2": "完结",
        
        # updater.py
        "up_check_fail": "无法检查更新，请检查网络连接",
        "up_latest": "当前已是最新版本 ({})",
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

        # web_app.py (New)
        "web_init": "初始化...",
        "web_connecting_book": "正在连接服务器获取书籍信息...",
        "web_book_info_fail_check": "获取书籍信息失败，请检查网络或书籍ID",
        "web_preparing_download": "准备下载《{}》...",
        "web_starting_engine": "启动下载引擎...",
        "web_download_success_path": "下载完成！已保存至 {}",
        "web_download_interrupted": "下载过程中断或失败",
        "web_download_exception": "下载异常: {}",
        "web_worker_error": "错误: {}",
        "web_module_loaded": "模块加载完成",
        "web_module_fail_msg": "模块加载失败",
        "web_queue_submitted": "已提交 {} 本书到下载队列",
        "web_queue_next": "本书完成（{}/{}），准备下一本...",
        "web_queue_next_fail": "本书失败（{}/{}），继续下一本...",
        "web_queue_complete": "队列下载完成，共 {} 本，已保存至 {}",
        "web_queue_complete_fail": "队列结束（可能有失败），共 {} 本，保存至 {}",

        # novel_downloader.py (New)
        "dl_full_content_error": "获取整书内容异常: {}",
        "dl_fetching_info": "正在获取书籍信息...",
        "dl_fetch_info_fail": "获取书籍信息失败",
        "dl_book_info_log": "书名: {}, 作者: {}",
        "dl_try_speed_mode": "正在尝试极速下载模式 (整书下载)...",
        "dl_speed_mode_success": "整书内容获取成功，正在解析...",
        "dl_speed_mode_parsed": "解析成功，共 {} 章",
        "dl_processing_chapters": "处理章节",
        "dl_process_complete": "章节处理完成",
        "dl_speed_mode_fail_parse": "解析失败或未找到章节，切换回普通模式",
        "dl_speed_mode_fail": "极速下载失败，切换回普通模式",
        "dl_fetch_list_fail": "获取章节列表失败",
        "dl_no_chapters_found": "未找到章节",
        "dl_found_chapters": "共找到 {} 章",
        "dl_range_log": "下载章节范围: {} 到 {}",
        "dl_selected_log": "已选择 {} 个特定章节",
        "dl_filter_error": "章节筛选出错: {}",
        "dl_all_downloaded": "所有章节已下载",
        "dl_start_download_log": "开始下载 {} 章...",
        "dl_progress_desc": "下载进度",
        "dl_progress_log": "已下载: {}/{}",
        "dl_analyzing_completeness": "正在分析下载完整性...",
        "dl_analyze_no_chapters": "没有下载到任何章节",
        "dl_analyze_summary": "完整性检查: 期望 {} 章，已下载 {} 章，缺失 {} 章",
        "dl_analyze_missing": "   缺失章节: {}...",
        "dl_analyze_pass": "完整性检查通过: 共 {} 章全部下载",
        "dl_analyze_gap": "检测到章节索引不连续，可能缺失: {}...",
        "dl_analyze_order_fail": "章节顺序检查: 发现 {} 处不连续，共缺少 {} 个位置",
        "dl_analyze_order_pass": "章节顺序检查通过",
        "dl_missing_retry": "发现 {} 个缺失章节，正在补充下载...",
        "dl_retry_log": "补充下载第 {} 次尝试，剩余 {} 章",
        "dl_retry_success": "所有缺失章节补充完成",
        "dl_retry_fail": "仍有 {} 章无法下载: {}...",
        "dl_verifying_order": "正在验证章节顺序...",
        "dl_intro_title": "简介",
        "dl_book_detail_title": "书籍详情",
        "label_author": "作者: ",

        # updater.py (New)
        "up_auto_update_msg": "发现新版本可用！\n\n📦 最新版本: {}\n📝 版本名称: {}\n\n📄 更新说明:\n{}\n\n🔗 下载地址:\n{}\n\n建议更新到最新版本以获得更好的体验和新功能！",
        "up_script_started": "更新脚本已启动，程序即将退出...",
        "up_create_script_fail": "创建更新脚本失败: {}",
        "up_platform_unsupported": "不支持的平台: {}",
        "up_not_frozen_linux": "自动更新仅支持打包后的程序",
        "up_new_missing_linux": "新版本文件不存在: {}",
    },
    "en": {
         # config.py
        "config_loading_local": "Loading local config...",
        "config_success": "Config loaded, API base URL: {}",
        "config_fail": "Failed to fetch remote config: {}",
        "config_server_error": "Warning: Cannot connect to config server, app may not work properly",
        "config_invalid_format": "Warning: Remote config format is invalid",
        "config_json_error": "Warning: Failed to parse remote config JSON: {}",
        
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
        "main_server_started": "Server started",
        "main_server_timeout": "Server start timeout",
        "main_opening_interface": "Opening application interface...",
        "main_flask_fail": "Flask app failed to start: {}",
        
        # web_app.py
        "web_update_status_dl": "Downloading: {}%",
        "web_update_status_connect": "Connecting to server...",
        "web_update_status_start": "Starting download...",
        "web_update_status_merging": "Merging files...",
        "web_update_connect_fail": "Cannot connect to download server, please check network or proxy settings",
        "web_update_complete": "Download complete, click 'Apply Update'",
        "web_update_fail": "Download failed: {}",
        "web_search_keyword_empty": "Please enter search keyword",
        "web_api_not_init": "API not initialized",
        "web_search_fail": "Search failed: {}",
        "web_book_id_empty": "Please enter Book ID or URL",
        "web_url_error": "Invalid URL format",
        "web_id_not_digit": "Book ID must be digits",
        "web_book_info_fail": "Failed to get book info",
        "web_chapter_list_fail": "Failed to get chapter list",
        "web_download_exists": "A download task is already running",
        
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
        "dl_batch_start": "Batch download started, {} books total",
        "dl_batch_cancelled": "Batch download cancelled",
        "dl_batch_downloading": "[{}/{}] Downloading: 《{}》",
        "dl_batch_progress": "Downloading book {} ...",
        "dl_batch_success": "《{}》 Downloaded",
        "dl_batch_fail": "《{}》 Failed",
        "dl_batch_exception": "《{}》 Exception: {}",
        "dl_batch_summary": "Batch Download Summary:",
        "dl_batch_stats_success": "   Success: {}",
        "dl_batch_stats_fail": "   Failed: {}",
        "dl_batch_stats_total": "   Total: {}",
        "dl_batch_fail_list": "Failed List:",
        "dl_batch_complete": "Completed {}/{}",
        "dl_chapter_title": "Chapter {}",
        "dl_unknown_book": "Unknown Title",
        "dl_unknown_author": "Unknown Author",
        "dl_no_intro": "No description",
        "dl_status_finished": "Finished",
        "dl_status_serializing": "Ongoing",
        "dl_status_completed_2": "Completed",
        
        # updater.py
        "up_check_fail": "Update check failed, check network",
        "up_latest": "Already latest version ({})",
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

        # web_app.py (New)
        "web_init": "Initializing...",
        "web_connecting_book": "Connecting to server to get book info...",
        "web_book_info_fail_check": "Failed to get book info, please check network or Book ID",
        "web_preparing_download": "Preparing download 《{}》...",
        "web_starting_engine": "Starting download engine...",
        "web_download_success_path": "Download complete! Saved to {}",
        "web_download_interrupted": "Download interrupted or failed",
        "web_download_exception": "Download Exception: {}",
        "web_worker_error": "Error: {}",
        "web_module_loaded": "Modules loaded",
        "web_module_fail_msg": "Module load failed",
        "web_queue_submitted": "Submitted {} books to download queue",
        "web_queue_next": "Completed ({}/{}), preparing next...",
        "web_queue_next_fail": "Failed ({}/{}), continuing...",
        "web_queue_complete": "Queue complete: {} books, saved to {}",
        "web_queue_complete_fail": "Queue finished (some may fail): {} books, saved to {}",

        # novel_downloader.py (New)
        "dl_full_content_error": "Get full content error: {}",
        "dl_fetching_info": "Fetching book info...",
        "dl_fetch_info_fail": "Failed to fetch book info",
        "dl_book_info_log": "Title: {}, Author: {}",
        "dl_try_speed_mode": "Trying Speed Mode (Full Download)...",
        "dl_speed_mode_success": "Full content retrieved, parsing...",
        "dl_speed_mode_parsed": "Parsed successfully, {} chapters total",
        "dl_processing_chapters": "Processing",
        "dl_process_complete": "Processing complete",
        "dl_speed_mode_fail_parse": "Parse failed or no chapters found, switching to Normal Mode",
        "dl_speed_mode_fail": "Speed Mode failed, switching to Normal Mode",
        "dl_fetch_list_fail": "Failed to fetch chapter list",
        "dl_no_chapters_found": "No chapters found",
        "dl_found_chapters": "Found {} chapters",
        "dl_range_log": "Range: {} to {}",
        "dl_selected_log": "Selected {} specific chapters",
        "dl_filter_error": "Filter error: {}",
        "dl_all_downloaded": "All chapters already downloaded",
        "dl_start_download_log": "Starting download {} chapters...",
        "dl_progress_desc": "Progress",
        "dl_progress_log": "Downloaded: {}/{}",
        "dl_analyzing_completeness": "Analyzing completeness...",
        "dl_analyze_no_chapters": "No chapters downloaded",
        "dl_analyze_summary": "Completeness Check: Expected {}, Downloaded {}, Missing {}",
        "dl_analyze_missing": "   Missing: {}...",
        "dl_analyze_pass": "Completeness Check Passed: {} chapters downloaded",
        "dl_analyze_gap": "Discontinuous indices detected, might miss: {}...",
        "dl_analyze_order_fail": "Order Check: Found {} gaps, missing {} spots",
        "dl_analyze_order_pass": "Order Check Passed",
        "dl_missing_retry": "Found {} missing chapters, retrying...",
        "dl_retry_log": "Retry {} attempt, remaining {}",
        "dl_retry_success": "All missing chapters downloaded",
        "dl_retry_fail": "Still unable to download {} chapters: {}...",
        "dl_verifying_order": "Verifying chapter order...",
        "dl_intro_title": "Introduction",
        "dl_book_detail_title": "Book Details",
        "label_author": "Author: ",

        # updater.py (New)
        "up_auto_update_msg": "New version available!\n\n📦 Version: {}\n📝 Name: {}\n\n📄 Changelog:\n{}\n\n🔗 Download:\n{}\n\nRecommended to update for better experience!",
        "up_script_started": "Update script started, app exiting...",
        "up_create_script_fail": "Failed to create update script: {}",
        "up_platform_unsupported": "Unsupported platform: {}",
        "up_not_frozen_linux": "Auto-update only supports frozen app",
        "up_new_missing_linux": "New version file missing: {}",
    }
}

def t(key, *args):
    """
    Get translated string
    Args:
        key: Message key
        *args: Format arguments
    """
    lang_code = get_current_lang()
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
