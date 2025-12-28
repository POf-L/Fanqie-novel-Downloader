const translations = {
    "zh": {
        // Header
        "app_title": "番茄小说下载器",
        
        // Tabs
        "tab_search": "搜索书籍",
        "tab_download": "手动下载",
        "tab_queue": "待下载",
        
        // Search Pane
        "search_placeholder": "输入书名或作者名搜索...",
        "btn_search": "搜索",
        "search_count_prefix": "找到 ",
        "search_count_suffix": " 本书籍",
        "btn_load_more": "加载更多",
        "search_no_results": "未找到相关书籍",
        "status_complete": "完结",
        "status_ongoing": "连载中",
        "meta_word_count_suffix": "万字",
        "meta_chapter_count_suffix": "章",
        "label_no_desc": "暂无简介",
        
        // Download Pane
        "placeholder_book_id": "例如：12345678 或 https://fanqienovel.com/12345678",
        "btn_add_to_queue": " 加入待下载",
        "btn_reset": "重置",

        // API Sources
        "api_auto_select": "自动选择（推荐）",
        "api_select_failed": "切换接口失败",
        "api_unavailable": "不可用",

        // Queue Pane
        "queue_summary_count": "待下载：{0} 本",
        "queue_empty": "暂无待下载任务",
        "queue_unknown_book": "未知书籍",
        "btn_remove_from_queue": "移除",
        "queue_item_chapters_all": "全部章节",
        "queue_item_chapters_range": "章节范围：{0}-{1}",
        "queue_item_chapters_manual": "手动选择：{0} 章",
        
        // Sidebar - Status
        "card_current_task": "当前任务",
        "status_ready": "准备就绪",
        "status_downloading": "下载中...",
        "status_completed": "已完成",
        "book_no_task": "暂无任务",
        
        // Sidebar - Log
        "card_log": "运行日志",
        "log_system_started": "系统已启动，等待操作...",
        
        // Chapter Modal / Inline Confirm
        "modal_chapter_title": "选择章节",
        "title_chapter_selection": "章节选择",
        "title_confirm_download": "确认下载",
        "radio_all_chapters": "全部章节",
        "radio_range_chapters": "范围选择",
        "radio_quick_range": "快速范围输入",
        "radio_manual_chapters": "手动选择",
        "label_start_chapter": "起始章节",
        "label_end_chapter": "结束章节",
        "label_quick_range": "章节范围",
        "placeholder_quick_range": "例如: 1-100, 150, 200-300",
        "hint_quick_range": "支持格式: 单个数字(5)、范围(1-100)、多个范围(1-10, 50-100)",
        "btn_apply_range": "应用范围",
        "quick_range_selected": "已选择 {0} 章",
        "quick_range_applied": "已应用范围，选中 {0} 章",
        "alert_enter_range": "请输入章节范围",
        "alert_no_chapters_selected": "没有选中任何章节",
        "alert_parse_range_fail": "解析范围失败",
        "label_total_chapters": "共 {0} 章",
        "text_author": "作者：",
        "text_fetching_book_info": "正在获取书籍信息...",
        "btn_cancel": "取消",
        "btn_confirm": "确定",
        "btn_confirm_add_to_queue": "确认添加到队列",
        "btn_select_all": "全选",
        "btn_select_none": "全不选",
        "btn_invert_selection": "反选",
        "text_fetching_chapters": "正在获取章节列表...",
        "text_fetch_chapter_fail": "获取章节失败",
        "text_no_changelog": "暂无更新说明",
        "label_selected_count": "已选: {0} / {1} 章",
        "label_dialog_selected": "已选 {0} 章",
        "btn_selected_count": "已选 {0} 章",
        "btn_select_chapters": "选择章节",
        
        // Confirm Dialog
        "confirm_title": "确认",
        "confirm_clear_queue": "确定要清空待下载队列吗？",
        
        // Update Modal
        "modal_update_title": "发现新版本",
        "btn_download_update": "立即下载",
        "update_btn_downloading": "下载中...",
        "update_btn_install": "安装更新",
        "update_btn_preparing": "准备中...",
        "update_btn_restarting": "正在重启...",
        "update_btn_retry": "重试",
        "update_btn_default": "下载",
        "update_progress_title": "下载进度",
        "update_status_connecting": "正在连接...",
        "update_status_complete": "下载完成",
        "update_status_ready": "准备下载...",
        "update_status_merging": "正在合并文件...",
        "update_warn_dont_close": "下载中请勿关闭窗口",
        "update_threads": "线程并行下载",
        "update_select_version": "选择下载版本:",
        "update_type_standalone": "完整版",
        "update_type_debug": "调试版",
        "update_type_standard": "标准版",
        "update_badge_rec": "推荐",
        
        // Folder Browser
        "folder_browser_title": "选择文件夹",
        
        // Alerts
        "alert_input_keyword": "请输入搜索关键词",
        "alert_input_book_id": "请输入书籍ID或URL",
        "alert_select_path": "请选择保存路径",
        "alert_id_number": "书籍ID应为纯数字",
        "alert_queue_empty": "待下载队列为空",
        "alert_download_in_progress": "当前已有下载任务正在进行",
        "alert_url_format_error": "URL格式错误",
        "alert_select_version": "请选择一个版本",
        "alert_apply_update_fail": "应用更新失败: ",
        "alert_download_fail": "下载失败: ",
        "alert_show_dialog_fail": "显示对话框失败",
        "alert_chapter_range_error": "章节范围错误",
        "alert_select_one_chapter": "请至少选择一个章节",
        "alert_url_error": "URL格式错误",
        
        // JS Messages / Logs
        "msg_app_start": "系统已启动，等待操作...",
        "msg_token_loaded": "访问令牌已加载",
        "msg_version_info": "版本信息: ",
        "msg_fetch_version_fail": "获取版本信息失败",
        "msg_init_app": "初始化应用...",
        "msg_module_loaded": "核心模块加载完成",
        "msg_module_fail": "模块加载失败: ",
        "msg_init_fail": "初始化失败",
        "msg_ready": "初始化完成，准备就绪",
        "msg_init_partial": "部分初始化完成",
        "msg_check_network": "请检查网络连接",
        "msg_request_fail": "请求失败: ",
        "msg_book_info_fail": "获取书籍信息失败: ",
        "msg_search_fail": "搜索失败: ",
        "msg_searching": "正在搜索: {0}",
        "msg_task_started": "下载任务已启动",
        "msg_added_to_queue": "已加入待下载：{0}",
        "msg_removed_from_queue": "已移除：{0}",
        "msg_queue_started": "已开始下载队列，共 {0} 本书",
        "msg_queue_cleared": "已清空待下载队列",
        "msg_loaded_from_file": "已从文件加载 {0} 本书籍",
        "msg_skipped_lines": "跳过 {0} 行",
        "alert_load_file_fail": "加载文件失败",
        "alert_no_valid_books": "文件中没有有效的书籍ID",
        "msg_download_cancelled": "下载已取消",
        "msg_cancel_fail": "取消下载失败: ",
        "msg_start_download_fail": "启动下载失败: ",
        "msg_save_path_updated": "保存路径已更新: {0}",
        "msg_open_folder_dialog": "打开文件夹选择...",
        "msg_folder_fail": "文件夹操作失败: ",
        "msg_settings_cleared": "设置已清除",
        "msg_file_path": "文件路径",
        "msg_book_already_downloaded": "该书籍已下载过",
        "title_duplicate_download": "重复下载提示",
        "msg_batch_duplicate_found": "发现 {0} 本书籍已下载过：",
        "msg_batch_duplicate_confirm": "是否继续下载？",
        "label_book_name": "书名",
        "label_download_time": "下载时间",
        "label_file_status": "文件状态",
        "status_file_exists": "文件存在",
        "status_file_missing": "文件已移动或删除",
        "btn_open_existing": "打开已有文件",
        "btn_download_anyway": "仍然下载",
        "log_get_chapter_list": "获取章节列表: ",
        "log_confirmed_selection": "已确认选择 {0} 个章节",
        "log_cancel_selection": "已取消章节选择",
        "log_search_success": "找到 {0} 本书籍",
        "log_search_no_results_x": "未找到相关书籍",
        "log_selected": "已选择: {0} (ID: {1})",
        "log_prepare_download": "准备下载: {0}",
        "log_chapter_range": "章节范围: {0} - {1}",
        "log_mode_manual": "手动选择: {0} 章",
        "log_download_all": "下载全部: {0}",
        "log_show_dialog_fail": "显示对话框失败: {0}",
        
        // API Sources
        "api_auto_select": "自动选择",
        "api_unavailable": "不可用",
        "api_checking_sources": "正在检测接口...",
        "api_check_failed": "接口检测失败: {0}",
        "api_select_failed": "接口选择失败",
        "api_status_auto": "自动选择接口中...",
        "api_status_manual": "手动选择接口: {0} ({1}ms)"
    },
    "en": {
        // Header
        "app_title": "Tomato Novel Downloader",
        
        // Tabs
        "tab_search": "Search Books",
        "tab_download": "Manual Download",
        "tab_queue": "Queue",
        
        // Search Pane
        "search_placeholder": "Enter book title or author...",
        "btn_search": "Search",
        "search_count_prefix": "Found ",
        "search_count_suffix": " books",
        "btn_load_more": "Load More",
        "search_no_results": "No books found",
        "status_complete": "Completed",
        "status_ongoing": "Ongoing",
        "meta_word_count_suffix": "0k words",
        "meta_chapter_count_suffix": " chapters",
        "label_no_desc": "No description available",
        
        // Download Pane
        "placeholder_book_id": "E.g., 12345678 or https://fanqienovel.com/12345678",
        "btn_add_to_queue": " Add to Queue",
        "btn_reset": "Reset",

        // API Sources
        "api_auto_select": "Auto (recommended)",
        "api_select_failed": "Failed to switch endpoint",
        "api_unavailable": "Unavailable",

        // Queue Pane
        "queue_summary_count": "Queue: {0} books",
        "queue_empty": "No pending downloads",
        "queue_unknown_book": "Unknown Book",
        "btn_remove_from_queue": "Remove",
        "queue_item_chapters_all": "All chapters",
        "queue_item_chapters_range": "Chapters: {0}-{1}",
        "queue_item_chapters_manual": "Selected: {0} chapters",
        
        // Sidebar - Status
        "card_current_task": "Current Task",
        "status_ready": "Ready",
        "status_downloading": "Downloading...",
        "status_completed": "Completed",
        "book_no_task": "No Task",
        
        // Sidebar - Log
        "card_log": "System Log",
        "log_system_started": "System initialized. Waiting for input...",
        
        // Chapter Modal / Inline Confirm
        "modal_chapter_title": "Select Chapters",
        "title_chapter_selection": "Chapter Selection",
        "title_confirm_download": "Confirm Download",
        "radio_all_chapters": "All Chapters",
        "radio_range_chapters": "Range Selection",
        "radio_quick_range": "Quick Range Input",
        "radio_manual_chapters": "Manual Selection",
        "label_start_chapter": "Start Chapter",
        "label_end_chapter": "End Chapter",
        "label_quick_range": "Chapter Range",
        "placeholder_quick_range": "E.g., 1-100, 150, 200-300",
        "hint_quick_range": "Formats: single(5), range(1-100), multiple(1-10, 50-100)",
        "btn_apply_range": "Apply Range",
        "quick_range_selected": "Selected {0} chapters",
        "quick_range_applied": "Applied range, selected {0} chapters",
        "alert_enter_range": "Please enter chapter range",
        "alert_no_chapters_selected": "No chapters selected",
        "alert_parse_range_fail": "Failed to parse range",
        "label_total_chapters": "{0} chapters",
        "text_author": "Author: ",
        "text_fetching_book_info": "Fetching book info...",
        "btn_cancel": "Cancel",
        "btn_confirm": "Confirm",
        "btn_confirm_add_to_queue": "Add to Queue",
        "btn_select_all": "Select All",
        "btn_select_none": "Select None",
        "btn_invert_selection": "Invert",
        "text_fetching_chapters": "Fetching chapter list...",
        "text_fetch_chapter_fail": "Failed to fetch chapters",
        "text_no_changelog": "No changelog available",
        "label_selected_count": "Selected: {0} / {1}",
        "label_dialog_selected": "Selected {0} ch",
        "btn_selected_count": "Selected {0} ch",
        "btn_select_chapters": "Select Chapters",
        
        // Confirm Dialog
        "confirm_title": "Confirm",
        "confirm_clear_queue": "Clear the download queue?",
        
        // Update Modal
        "modal_update_title": "New Version Found",
        "btn_download_update": "Download Now",
        "update_btn_downloading": "Downloading...",
        "update_btn_install": "Install Update",
        "update_btn_preparing": "Preparing...",
        "update_btn_restarting": "Restarting...",
        "update_btn_retry": "Retry",
        "update_btn_default": "Download",
        "update_progress_title": "Download Progress",
        "update_status_connecting": "Connecting...",
        "update_status_complete": "Download Complete",
        "update_status_ready": "Ready to download...",
        "update_status_merging": "Merging files...",
        "update_warn_dont_close": "Do not close while downloading",
        "update_threads": "threads downloading",
        "update_select_version": "Select Version:",
        "update_type_standalone": "Standalone",
        "update_type_debug": "Debug",
        "update_type_standard": "Standard",
        "update_badge_rec": "Recommended",
        
        // Folder Browser
        "folder_browser_title": "Select Folder",
        
        // Alerts
        "alert_input_keyword": "Please enter search keyword",
        "alert_input_book_id": "Please enter Book ID or URL",
        "alert_select_path": "Please select save path",
        "alert_id_number": "Book ID must be numeric",
        "alert_queue_empty": "Queue is empty",
        "alert_download_in_progress": "A download task is already running",
        "alert_url_format_error": "URL format error",
        "alert_select_version": "Please select a version",
        "alert_apply_update_fail": "Failed to apply update: ",
        "alert_download_fail": "Download failed: ",
        "alert_show_dialog_fail": "Failed to show dialog",
        "alert_chapter_range_error": "Invalid chapter range",
        "alert_select_one_chapter": "Please select at least one chapter",
        "alert_url_error": "Invalid URL format",
        
        // JS Messages / Logs
        "msg_version_info": "Version: ",
        "msg_app_start": "System started, waiting for action...",
        "msg_token_loaded": "Access token loaded",
        "msg_fetch_version_fail": "Failed to fetch version",
        "msg_init_app": "Initializing...",
        "msg_module_loaded": "Core modules loaded",
        "msg_module_fail": "Module load failed: ",
        "msg_init_fail": "Initialization failed",
        "msg_ready": "Initialization complete, ready",
        "msg_init_partial": "Partial initialization complete",
        "msg_check_network": "Please check network connection",
        "msg_request_fail": "Request failed: ",
        "msg_book_info_fail": "Failed to get book info: ",
        "msg_search_fail": "Search failed: ",
        "msg_searching": "Searching: {0}",
        "msg_task_started": "Download started",
        "msg_added_to_queue": "Added to queue: {0}",
        "msg_removed_from_queue": "Removed: {0}",
        "msg_queue_started": "Queue started: {0} books",
        "msg_queue_cleared": "Queue cleared",
        "msg_loaded_from_file": "Loaded {0} books from file",
        "msg_skipped_lines": "skipped {0} lines",
        "alert_load_file_fail": "Failed to load file",
        "alert_no_valid_books": "No valid book IDs in file",
        "msg_download_cancelled": "Download cancelled",
        "msg_cancel_fail": "Cancel failed: ",
        "msg_start_download_fail": "Failed to start download: ",
        "msg_save_path_updated": "Save path updated: {0}",
        "msg_open_folder_dialog": "Opening folder dialog...",
        "msg_folder_fail": "Folder operation failed: ",
        "msg_settings_cleared": "Settings cleared",
        "msg_file_path": "File path",
        "msg_book_already_downloaded": "This book has been downloaded before",
        "title_duplicate_download": "Duplicate Download",
        "msg_batch_duplicate_found": "Found {0} books already downloaded:",
        "msg_batch_duplicate_confirm": "Continue downloading?",
        "label_book_name": "Book Name",
        "label_download_time": "Download Time",
        "label_file_status": "File Status",
        "status_file_exists": "File exists",
        "status_file_missing": "File moved or deleted",
        "btn_open_existing": "Open Existing",
        "btn_download_anyway": "Download Anyway",
        "log_get_chapter_list": "Fetching chapter list: ",
        "log_confirmed_selection": "Confirmed {0} chapters",
        "log_cancel_selection": "Chapter selection cancelled",
        "log_search_success": "Found {0} books",
        "log_search_no_results_x": "No books found",
        "log_selected": "Selected: {0} (ID: {1})",
        "log_prepare_download": "Preparing download: {0}",
        "log_chapter_range": "Chapter range: {0} - {1}",
        "log_mode_manual": "Manual selection: {0} chapters",
        "log_download_all": "Download all: {0}",
        "log_show_dialog_fail": "Failed to show dialog: {0}",
        
        // API Sources
        "api_auto_select": "Auto Select",
        "api_unavailable": "Unavailable",
        "api_checking_sources": "Checking sources...",
        "api_check_failed": "Source check failed: {0}",
        "api_select_failed": "Source selection failed",
        "api_status_auto": "Auto selecting source...",
        "api_status_manual": "Manual source: {0} ({1}ms)"
    }
};

class I18n {
    constructor() {
        this.lang = localStorage.getItem('app_language') || 'zh';
        this.observers = [];
        this.syncToBackend(this.lang);
    }
    
    t(key, ...args) {
        let value = translations[this.lang]?.[key] || key;
        if (args.length > 0) {
            args.forEach((arg, index) => {
                value = value.replace(new RegExp(`\\{${index}\\}`, 'g'), arg);
            });
        }
        return value;
    }
    
    setLanguage(lang) {
        if (this.lang === lang) return;
        this.lang = lang;
        localStorage.setItem('app_language', lang);
        this.updatePage();
        this.notifyObservers();
        this.syncToBackend(lang);
    }
    
    syncToBackend(lang) {
        fetch('/api/language', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: lang })
        }).catch(() => {});
    }
    
    toggleLanguage() {
        this.setLanguage(this.lang === 'zh' ? 'en' : 'zh');
    }
    
    updatePage() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (el.tagName === 'INPUT' && el.hasAttribute('placeholder')) {
                el.setAttribute('placeholder', this.t(key));
            } else if (el.hasAttribute('title')) {
                el.setAttribute('title', this.t(key));
                if (el.children.length === 0 && el.textContent.trim()) {
                    el.textContent = this.t(key);
                }
            } else if (el.children.length === 0) {
                el.textContent = this.t(key);
                if (el.hasAttribute('data-text')) {
                    el.setAttribute('data-text', this.t(key));
                }
            } else {
                el.childNodes.forEach(node => {
                    if (node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0) {
                        const hasLeadingSpace = node.textContent.startsWith(' ');
                        node.textContent = (hasLeadingSpace ? ' ' : '') + this.t(key).trim();
                    }
                });
                const label = el.querySelector('.tab-label');
                if (label) label.textContent = this.t(key);
            }
        });
        document.title = this.t('app_title');
    }
    
    translateBackendMsg(msg) {
        if (this.lang === 'zh') return msg;
        if (msg.includes('下载完成')) return msg.replace('下载完成', 'Download Completed');
        if (msg.includes('下载失败')) return msg.replace('下载失败', 'Download Failed');
        if (msg.includes('开始下载')) return msg.replace('开始下载', 'Start Download');
        if (msg.includes('正在获取书籍信息')) return 'Fetching book info...';
        if (msg.includes('正在解析章节')) return 'Parsing chapters...';
        if (msg.includes('正在下载章节')) return 'Downloading chapters...';
        if (msg.includes('合并文件')) return 'Merging files...';
        return msg;
    }
    
    onLanguageChange(callback) {
        this.observers.push(callback);
    }
    
    notifyObservers() {
        this.observers.forEach(cb => cb(this.lang));
    }
}

const i18n = new I18n();
