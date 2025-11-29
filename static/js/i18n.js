const translations = {
    "zh": {
        // SCP Banner
        "scp_warning": "警告：严禁未授权访问 // 机密级别：4级",
        "top_secret": "绝密档案",
        "secure_connection": "安全连接 // 已加密",
        
        // Header
        "app_title": "番茄小说下载器",
        "github_link": "GitHub",
        "title_toggle_style": "切换风格",
        "title_minimize": "最小化",
        "title_maximize": "最大化",
        "title_close": "关闭",
        "style_8bit": "8-BIT",
        "style_scp": "SCP",
        
        // Tabs
        "tab_search": "搜索书籍",
        "tab_download": "手动下载",
        
        // Search Pane
        "search_placeholder": "输入书名或作者名搜索...",
        "btn_search": "搜索",
        "search_count_prefix": "找到 ",
        "search_count_suffix": " 本书籍",
        "btn_clear": "清除结果",
        "btn_load_more": "加载更多",
        "search_no_results": "未找到相关书籍",
        "status_complete": "完结",
        "status_ongoing": "连载中",
        "meta_word_count_suffix": "万字",
        "meta_chapter_count_suffix": "章",
        "label_no_desc": "暂无简介",
        
        // Download Pane
        "download_config_title": "手动下载配置",
        "download_config_desc": "输入书籍 ID 或链接进行下载",
        "label_book_id": "书籍 ID / URL",
        "placeholder_book_id": "例如：12345678 或 https://fanqienovel.com/...",
        "label_save_path": "保存路径",
        "placeholder_save_path": "选择保存目录",
        "btn_browse": "浏览...",
        "label_format": "文件格式",
        "btn_start_download": " 开始下载",
        "btn_cancel_download": " 取消下载",
        "btn_reset": "重置",
        
        // Sidebar - Status
        "card_current_task": "当前任务",
        "status_ready": "准备就绪",
        "status_downloading": "下载中...",
        "status_completed": "√ 已完成",
        "book_no_task": "暂无任务",
        "label_progress": "下载进度",
        
        // Sidebar - Log
        "card_log": "运行日志",
        "log_system_started": "系统已启动，等待操作...",
        
        // Chapter Modal
        "modal_chapter_title": "[#] 选择章节",
        "btn_select_all": "全选",
        "btn_select_none": "全不选",
        "btn_invert_selection": "反选",
        "selected_count_prefix": "已选: ",
        "selected_count_suffix": " 章",
        "empty_chapter_list": "请先获取章节列表",
        "btn_cancel": "取消",
        "btn_confirm": "确定",
        "text_fetching_chapters": "正在获取章节列表...",
        "text_fetch_chapter_fail": "获取章节失败",
        "text_no_changelog": "暂无更新说明",
        "label_selected_count": "已选: {0} / {1} 章",
        "btn_selected_count": "= 已选 {0} 章",
        "btn_select_chapters": "= 选择章节",
        
        // Confirm Dialog
        "label_manual_selected": "√ 已手动选择 {0} 个章节",
        "hint_manual_mode": "提示：自定义选择模式下不支持\"整书极速下载\"",
        "btn_reselect": "重新选择章节",
        "radio_all_chapters": "下载全部章节 (支持极速模式)",
        "radio_range_chapters": "自定义章节范围",
        "radio_manual_chapters": "手动选择章节",
        "label_start_chapter": "起始章节:",
        "label_end_chapter": "结束章节:",
        "label_dialog_selected": "已选: {0} 章",
        "title_confirm_download": "+ 确认下载",
        "label_author": "作者: ",
        "label_total_chapters": "共 {0} 章",
        "title_chapter_selection": "章节选择",
        
        // Update Modal
        "modal_update_title": "[!] 发现新版本",
        "label_current_version": "当前版本：",
        "label_latest_version": "最新版本：",
        "label_update_desc": "更新说明：",
        "btn_download_update": "立即下载",
        "btn_later": "稍后提醒",
        "update_select_version": "选择下载版本:",
        "update_type_standalone": "完整版",
        "update_type_debug": "调试版",
        "update_type_standard": "标准版",
        "update_badge_rec": "推荐",
        "update_btn_downloading": "正在下载...",
        "update_progress_title": "> DOWNLOADING_UPDATE...",
        "update_status_connecting": "CONNECTING...",
        "update_warn_dont_close": "* DO NOT CLOSE *",
        "update_btn_install": "[ INSTALL & RESTART ]",
        "update_status_complete": "√ DOWNLOAD COMPLETE",
        "update_btn_preparing": "正在准备更新...",
        "update_btn_restarting": "更新中，程序即将重启...",
        "update_btn_retry": "重新下载",
        "update_status_ready": "准备下载...",
        "update_status_fail": "下载失败: ",
        "update_btn_default": "下载更新",
        
        // Alerts
        "alert_input_keyword": "请输入搜索关键词",
        "alert_input_book_id": "请输入书籍ID或URL",
        "alert_select_path": "请选择保存路径",
        "alert_url_error": "URL格式错误，请使用正确的Fanqie小说URL",
        "alert_id_number": "书籍ID应为纯数字",
        "alert_fetch_fail": "获取书籍信息失败，请检查ID是否正确",
        "alert_chapter_range_error": "起始章节不能大于结束章节",
        "alert_select_one_chapter": "请至少选择一个章节",
        "alert_show_dialog_fail": "显示确认窗口失败，请查看控制台日志",
        "confirm_cancel_download": "确定要取消下载吗？",
        "confirm_clear_settings": "确定要清理所有设置吗？",
        "alert_url_format_error": "URL格式错误",
        "alert_select_version": "请选择一个版本",
        "alert_apply_update_fail": "应用更新失败: ",
        "alert_download_fail": "下载失败: ",
        
        // JS Messages / Logs
        "msg_version_info": "✓ 版本信息: ",
        "msg_fetch_version_fail": "! 获取版本信息失败",
        "msg_app_start": "> 应用启动...",
        "msg_token_loaded": "✓ 访问令牌已加载",
        "msg_init_app": "* 初始化应用...",
        "msg_module_loaded": "√ 核心模块加载完成",
        "msg_module_fail": "! 模块加载失败: ",
        "msg_init_fail": "X 初始化失败",
        "msg_request_fail": "X 请求失败: ",
        "msg_book_info_fail": "X 获取书籍信息失败: ",
        "msg_search_fail": "X 搜索失败: ",
        "msg_task_started": "√ 下载任务已启动",
        "msg_download_cancelled": "■ 下载已取消",
        "msg_cancel_fail": "X 取消下载失败: ",
        "msg_folder_fail": "X 文件夹选择失败: ",
        "msg_select_chapter_warn": "请至少选择一章",
        "msg_open_folder_dialog": "> 打开文件夹选择对话框...",
        "msg_save_path_updated": "√ 保存路径已更新: ",
        "msg_searching": "? 正在搜索: ",
        "msg_start_download_fail": "X 启动下载失败: ",
        "msg_settings_cleared": "~ 设置已清理",
        "msg_ready": "准备就绪，请输入书籍信息开始下载",
        "msg_init_partial": "! 应用初始化完成，但部分功能可能不可用",
        "msg_check_network": "如遇到问题，请检查网络连接或重启应用",
        "log_prepare_download": "# 准备下载《{0}》",
        "log_mode_manual": "> 模式: 手动选择 ({0} 章)",
        "log_chapter_range": "> 章节范围: 第 {0} 章 - 第 {1} 章",
        "log_download_all": "# 准备下载《{0}》全部章节",
        "log_save_path": "$ 保存路径: ",
        "log_file_format": "= 文件格式: ",
        "log_show_dialog_fail": "X 显示确认窗口失败: ",
        "log_selected": "+ 已选择: {0} (ID: {1})",
        "log_get_chapter_list": "# 获取章节列表: ",
        "log_confirmed_selection": "√ 已确认选择 {0} 个章节",
        "log_cancel_selection": "√ 已取消章节选择 (默认下载全部)",
        "log_scp_access": "> 正在访问 SCP 数据库...",
        "log_scp_revert": "> 正在恢复 8-BIT 系统...",
        "log_search_success": "找到 {0} 本书籍",
        "log_search_no_results_x": "X 未找到相关书籍",
        
        // Common Backend Messages Mappings (Frontend translation)
        "backend_msg_download_complete": "下载完成",
        "backend_msg_download_error": "下载出错"
    },
    "en": {
        // SCP Banner
        "scp_warning": "WARNING: UNAUTHORIZED ACCESS IS STRICTLY PROHIBITED // CLASSIFIED: LEVEL 4",
        "top_secret": "TOP SECRET",
        "secure_connection": "SECURE CONNECTION // ENCRYPTED",
        
        // Header
        "app_title": "Tomato Novel Downloader",
        "github_link": "GitHub",
        "title_toggle_style": "Switch Style",
        "title_minimize": "Minimize",
        "title_maximize": "Maximize",
        "title_close": "Close",
        "style_8bit": "8-BIT",
        "style_scp": "SCP",
        
        // Tabs
        "tab_search": "Search Books",
        "tab_download": "Manual Download",
        
        // Search Pane
        "search_placeholder": "Enter book title or author...",
        "btn_search": "Search",
        "search_count_prefix": "Found ",
        "search_count_suffix": " books",
        "btn_clear": "Clear",
        "btn_load_more": "Load More",
        "search_no_results": "No books found",
        "status_complete": "Completed",
        "status_ongoing": "Ongoing",
        "meta_word_count_suffix": "0k words",
        "meta_chapter_count_suffix": " chapters",
        "label_no_desc": "No description available",
        
        // Download Pane
        "download_config_title": "Download Config",
        "download_config_desc": "Enter Book ID or URL to download",
        "label_book_id": "Book ID / URL",
        "placeholder_book_id": "E.g., 12345678 or https://fanqienovel.com/...",
        "label_save_path": "Save Path",
        "placeholder_save_path": "Select save directory",
        "btn_browse": "Browse...",
        "label_format": "Format",
        "btn_start_download": " Download",
        "btn_cancel_download": " Cancel",
        "btn_reset": "Reset",
        
        // Sidebar - Status
        "card_current_task": "Current Task",
        "status_ready": "Ready",
        "status_downloading": "Downloading...",
        "status_completed": "√ Completed",
        "book_no_task": "No Task",
        "label_progress": "Progress",
        
        // Sidebar - Log
        "card_log": "System Log",
        "log_system_started": "System initialized. Waiting for input...",
        
        // Chapter Modal
        "modal_chapter_title": "[#] Select Chapters",
        "btn_select_all": "All",
        "btn_select_none": "None",
        "btn_invert_selection": "Invert",
        "selected_count_prefix": "Selected: ",
        "selected_count_suffix": " chapters",
        "empty_chapter_list": "Please fetch chapter list first",
        "btn_cancel": "Cancel",
        "btn_confirm": "Confirm",
        "text_fetching_chapters": "Fetching chapter list...",
        "text_fetch_chapter_fail": "Failed to fetch chapters",
        "text_no_changelog": "No changelog available",
        "label_selected_count": "Selected: {0} / {1}",
        "btn_selected_count": "= Selected {0} ch",
        "btn_select_chapters": "= Select Chapters",
        
        // Confirm Dialog
        "label_manual_selected": "√ Manually selected {0} chapters",
        "hint_manual_mode": "Tip: 'Full Book Speed Download' is not supported in custom selection mode",
        "btn_reselect": "Reselect Chapters",
        "radio_all_chapters": "Download All Chapters (Speed Mode supported)",
        "radio_range_chapters": "Custom Chapter Range",
        "radio_manual_chapters": "Manual Chapter Selection",
        "label_start_chapter": "Start Chapter:",
        "label_end_chapter": "End Chapter:",
        "label_dialog_selected": "Selected: {0} ch",
        "title_confirm_download": "+ Confirm Download",
        "label_author": "Author: ",
        "label_total_chapters": "Total {0} chapters",
        "title_chapter_selection": "Chapter Selection",
        
        // Update Modal
        "modal_update_title": "[!] New Version Found",
        "label_current_version": "Current: ",
        "label_latest_version": "Latest: ",
        "label_update_desc": "Changelog:",
        "btn_download_update": "Download Now",
        "btn_later": "Remind Later",
        "update_select_version": "Select Version:",
        "update_type_standalone": "Standalone",
        "update_type_debug": "Debug",
        "update_type_standard": "Standard",
        "update_badge_rec": "Recommended",
        "update_btn_downloading": "Downloading...",
        "update_progress_title": "> DOWNLOADING_UPDATE...",
        "update_status_connecting": "CONNECTING...",
        "update_warn_dont_close": "* DO NOT CLOSE *",
        "update_btn_install": "[ INSTALL & RESTART ]",
        "update_status_complete": "√ DOWNLOAD COMPLETE",
        "update_btn_preparing": "Preparing update...",
        "update_btn_restarting": "Updating, restarting...",
        "update_btn_retry": "Retry Download",
        "update_status_ready": "Ready to download...",
        "update_status_fail": "Download failed: ",
        "update_btn_default": "Download Update",
        
        // Alerts
        "alert_input_keyword": "Please enter search keyword",
        "alert_input_book_id": "Please enter Book ID or URL",
        "alert_select_path": "Please select save path",
        "alert_url_error": "Invalid URL. Please use a valid Fanqie Novel URL",
        "alert_id_number": "Book ID must be numeric",
        "alert_fetch_fail": "Failed to fetch book info. Please check the ID.",
        "alert_chapter_range_error": "Start chapter cannot be greater than end chapter",
        "alert_select_one_chapter": "Please select at least one chapter",
        "alert_show_dialog_fail": "Failed to show confirmation dialog. Check console logs.",
        "confirm_cancel_download": "Are you sure you want to cancel the download?",
        "confirm_clear_settings": "Are you sure you want to clear all settings?",
        "alert_url_format_error": "URL format error",
        "alert_select_version": "Please select a version",
        "alert_apply_update_fail": "Failed to apply update: ",
        "alert_download_fail": "Download failed: ",
        
        // JS Messages / Logs
        "msg_version_info": "✓ Version: ",
        "msg_fetch_version_fail": "! Failed to fetch version",
        "msg_app_start": "> Starting app...",
        "msg_token_loaded": "✓ Access token loaded",
        "msg_init_app": "* Initializing...",
        "msg_module_loaded": "√ Core modules loaded",
        "msg_module_fail": "! Module load failed: ",
        "msg_init_fail": "X Initialization failed",
        "msg_request_fail": "X Request failed: ",
        "msg_book_info_fail": "X Failed to get book info: ",
        "msg_search_fail": "X Search failed: ",
        "msg_task_started": "√ Download started",
        "msg_download_cancelled": "■ Download cancelled",
        "msg_cancel_fail": "X Cancel failed: ",
        "msg_folder_fail": "X Folder selection failed: ",
        "msg_select_chapter_warn": "Please select at least one chapter",
        "msg_open_folder_dialog": "> Opening folder selection dialog...",
        "msg_save_path_updated": "√ Save path updated: ",
        "msg_searching": "? Searching for: ",
        "msg_start_download_fail": "X Failed to start download: ",
        "msg_settings_cleared": "~ Settings cleared",
        "msg_ready": "Ready. Enter book info to start download",
        "msg_init_partial": "! App initialized, but some features may be unavailable",
        "msg_check_network": "If you encounter issues, check network or restart app",
        "log_prepare_download": "# Preparing download: <{0}>",
        "log_mode_manual": "> Mode: Manual ({0} chapters)",
        "log_chapter_range": "> Range: Ch {0} - Ch {1}",
        "log_download_all": "# Preparing to download all chapters of <{0}>",
        "log_save_path": "$ Save Path: ",
        "log_file_format": "= Format: ",
        "log_show_dialog_fail": "X Failed to show dialog: ",
        "log_selected": "+ Selected: {0} (ID: {1})",
        "log_get_chapter_list": "# Fetching chapter list: ",
        "log_confirmed_selection": "√ Confirmed {0} chapters",
        "log_cancel_selection": "√ Selection cancelled (Download all by default)",
        "log_scp_access": "> ACCESSING SCP DATABASE...",
        "log_scp_revert": "> REVERTING TO 8-BIT SYSTEMS...",
        "log_search_success": "Found {0} books",
        "log_search_no_results_x": "X No books found",
        
        // Common Backend Messages Mappings
        "backend_msg_download_complete": "Download Completed",
        "backend_msg_download_error": "Download Error"
    }
};

class I18n {
    constructor() {
        this.lang = localStorage.getItem('app_language') || 'zh';
        this.observers = [];
        
        // 启动时同步语言到后端
        this.syncToBackend(this.lang);
    }
    
    t(key, ...args) {
        let value = key;
        if (translations[this.lang] && translations[this.lang][key]) {
            value = translations[this.lang][key];
        }
        
        // Handle variable substitution {0}, {1}, etc.
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
        
        // 同步语言设置到后端
        this.syncToBackend(lang);
    }
    
    syncToBackend(lang) {
        fetch('/api/language', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: lang })
        }).catch(err => console.warn('Failed to sync language to backend:', err));
    }
    
    toggleLanguage() {
        this.setLanguage(this.lang === 'zh' ? 'en' : 'zh');
    }
    
    updatePage() {
        // Update static elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            // Handle inputs with placeholders separately
            if (el.tagName === 'INPUT' && el.hasAttribute('placeholder')) {
                el.setAttribute('placeholder', this.t(key));
            } else if (el.hasAttribute('title')) {
                // Some elements might use title
                el.setAttribute('title', this.t(key));
                // If it also has content, continue to update content
                if (el.children.length === 0 && el.textContent.trim()) {
                     el.textContent = this.t(key);
                }
            } else {
                // For buttons with icons, we want to preserve the icon
                if (el.children.length === 0) {
                    el.textContent = this.t(key);
                    // Update data-text for glitch effect
                    if (el.hasAttribute('data-text')) {
                        el.setAttribute('data-text', this.t(key));
                    }
                } else {
                    let textNodeFound = false;
                    el.childNodes.forEach(node => {
                        if (node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0) {
                            // Keep leading spaces if they exist in current text
                            const hasLeadingSpace = node.textContent.startsWith(' ');
                            node.textContent = (hasLeadingSpace ? ' ' : '') + this.t(key).trim(); 
                            textNodeFound = true;
                        }
                    });
                    
                    // If no text node found but we have children, maybe it's inside a span?
                    // E.g. tab-label
                    const label = el.querySelector('.tab-label');
                    if (label) {
                        label.textContent = this.t(key);
                        textNodeFound = true;
                    }
                }
            }
        });
        
        // Update document title
        document.title = this.t('app_title');
    }
    
    // Helper to translate backend messages if possible
    translateBackendMsg(msg) {
        // This is a naive implementation to catch common phrases
        if (this.lang === 'zh') return msg; // Backend is Chinese default
        
        // Simple mapping for English
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
