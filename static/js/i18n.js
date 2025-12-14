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
        
        // Chapter Modal
        "modal_chapter_title": "选择章节",
        "btn_cancel": "取消",
        "btn_confirm": "确定",
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
        
        // JS Messages / Logs
        "msg_version_info": "版本信息: ",
        "msg_fetch_version_fail": "获取版本信息失败",
        "msg_init_app": "初始化应用...",
        "msg_module_loaded": "核心模块加载完成",
        "msg_module_fail": "模块加载失败: ",
        "msg_init_fail": "初始化失败",
        "msg_request_fail": "请求失败: ",
        "msg_book_info_fail": "获取书籍信息失败: ",
        "msg_search_fail": "搜索失败: ",
        "msg_task_started": "下载任务已启动",
        "msg_added_to_queue": "已加入待下载：{0}",
        "msg_removed_from_queue": "已移除：{0}",
        "msg_queue_started": "已开始下载队列，共 {0} 本书",
        "msg_queue_cleared": "已清空待下载队列",
        "msg_download_cancelled": "下载已取消",
        "msg_cancel_fail": "取消下载失败: ",
        "msg_start_download_fail": "启动下载失败: ",
        "msg_save_path_updated": "保存路径已更新: {0}",
        "log_get_chapter_list": "获取章节列表: ",
        "log_confirmed_selection": "已确认选择 {0} 个章节",
        "log_search_success": "找到 {0} 本书籍"
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
        
        // Chapter Modal
        "modal_chapter_title": "Select Chapters",
        "btn_cancel": "Cancel",
        "btn_confirm": "Confirm",
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
        
        // JS Messages / Logs
        "msg_version_info": "Version: ",
        "msg_fetch_version_fail": "Failed to fetch version",
        "msg_init_app": "Initializing...",
        "msg_module_loaded": "Core modules loaded",
        "msg_module_fail": "Module load failed: ",
        "msg_init_fail": "Initialization failed",
        "msg_request_fail": "Request failed: ",
        "msg_book_info_fail": "Failed to get book info: ",
        "msg_search_fail": "Search failed: ",
        "msg_task_started": "Download started",
        "msg_added_to_queue": "Added to queue: {0}",
        "msg_removed_from_queue": "Removed: {0}",
        "msg_queue_started": "Queue started: {0} books",
        "msg_queue_cleared": "Queue cleared",
        "msg_download_cancelled": "Download cancelled",
        "msg_cancel_fail": "Cancel failed: ",
        "msg_start_download_fail": "Failed to start download: ",
        "msg_save_path_updated": "Save path updated: {0}",
        "log_get_chapter_list": "Fetching chapter list: ",
        "log_confirmed_selection": "Confirmed {0} chapters",
        "log_search_success": "Found {0} books"
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
