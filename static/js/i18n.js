const translations = {
    "zh": {
        // SCP Banner
        "scp_warning": "警告：严禁未授权访问 // 机密级别：4级",
        "top_secret": "绝密档案",
        "secure_connection": "安全连接 // 已加密",
        
        // Header
        "app_title": "番茄小说下载器",
        "github_link": "GitHub",
        
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
        
        // Update Modal
        "modal_update_title": "[!] 发现新版本",
        "label_current_version": "当前版本：",
        "label_latest_version": "最新版本：",
        "label_update_desc": "更新说明：",
        "btn_download_update": "立即下载",
        "btn_later": "稍后提醒",
        
        // JS Messages
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
        
        "msg_ready": "准备就绪，请输入书籍信息开始下载",
        "msg_init_partial": "! 应用初始化完成，但部分功能可能不可用",
        "msg_check_network": "如遇到问题，请检查网络连接或重启应用",
        
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
        
        // Update Modal
        "modal_update_title": "[!] New Version Found",
        "label_current_version": "Current: ",
        "label_latest_version": "Latest: ",
        "label_update_desc": "Changelog:",
        "btn_download_update": "Download Now",
        "btn_later": "Remind Later",
        
        // JS Messages
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
        
        "msg_ready": "Ready. Enter book info to start download",
        "msg_init_partial": "! App initialized, but some features may be unavailable",
        "msg_check_network": "If you encounter issues, check network or restart app",
        
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
    
    t(key) {
        if (translations[this.lang] && translations[this.lang][key]) {
            return translations[this.lang][key];
        }
        return key; // Fallback to key if not found
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
            } else {
                // For buttons with icons, we want to preserve the icon
                // This is a bit tricky. We assume text is in a span or text node
                // For this project, buttons often have <span class="icon">...</span> Text
                // Let's try to find the text node or a span that holds the text
                
                // Simple strategy: if element has children, assume specific structure or just replace text content if simple
                if (el.children.length === 0) {
                    el.textContent = this.t(key);
                    // Update data-text for glitch effect
                    if (el.hasAttribute('data-text')) {
                        el.setAttribute('data-text', this.t(key));
                    }
                } else {
                    // Custom handling for elements with icons
                    // Try to find a text node to update, or a specific class like .text-content
                    // If button has icon inside, we might need to wrap text in span or identify it
                    
                    // For this specific project:
                    // Button structure: <span class="icon">...</span> Text
                    // We can iterate childNodes and update the text node
                    let textNodeFound = false;
                    el.childNodes.forEach(node => {
                        if (node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0) {
                            node.textContent = ' ' + this.t(key).trim(); // Add space for separation from icon
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
                    
                    if (!textNodeFound && el.querySelector('.format-name')) {
                         // For format radio labels
                         // Actually format names like TXT/EPUB usually don't need translation or are simple
                    }
                }
            }
        });
        
        // Update document title
        document.title = this.t('app_title');
        
        // Update specific specialized elements if needed
        const versionLabel = document.querySelector('.version-tag');
        if (versionLabel && versionLabel.firstChild.nodeType === Node.TEXT_NODE) {
            // versionLabel.firstChild.textContent = 'v'; // 'v' is universal
        }
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
