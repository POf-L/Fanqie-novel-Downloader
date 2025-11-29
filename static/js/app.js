/* ===================== 全局状态管理 ===================== */

const AppState = {
    isDownloading: false,
    currentProgress: 0,
    savePath: '',
    accessToken: '',
    selectedChapters: null, // 存储选中的章节索引数组
    
    setDownloading(value) {
        this.isDownloading = value;
        this.updateUIState();
    },
    
    setProgress(value) {
        this.currentProgress = value;
    },
    
    setSavePath(path) {
        this.savePath = path;
        document.getElementById('savePath').value = path;
    },
    
    setAccessToken(token) {
        this.accessToken = token;
    },
    
    updateUIState() {
        const downloadBtn = document.getElementById('downloadBtn');
        const cancelBtn = document.getElementById('cancelBtn');
        const bookIdInput = document.getElementById('bookId');
        const browseBtn = document.getElementById('browseBtn');
        
        if (this.isDownloading) {
            downloadBtn.style.display = 'none';
            cancelBtn.style.display = 'inline-block';
            bookIdInput.disabled = true;
            browseBtn.disabled = true;
        } else {
            downloadBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'none';
            bookIdInput.disabled = false;
            browseBtn.disabled = false;
        }
    }
};

/* ===================== 版本管理 ===================== */

async function fetchVersion(retryCount = 0) {
    const versionEl = document.getElementById('version');
    if (!versionEl) return;
    
    try {
        // 添加时间戳防止缓存
        const response = await fetch(`/api/version?t=${new Date().getTime()}`);
        const data = await response.json();
        if (data.success && data.version) {
            versionEl.textContent = data.version;
            logger.log(i18n.t('msg_version_info') + data.version);
        }
    } catch (e) {
        console.error('获取版本信息失败:', e);
        // 重试最多3次
        if (retryCount < 3) {
            setTimeout(() => fetchVersion(retryCount + 1), 1000);
        } else {
            logger.log(i18n.t('msg_fetch_version_fail'));
        }
    }
}

/* ===================== 日志管理 ===================== */

class Logger {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.maxEntries = 100;
    }
    
    log(message) {
        const entry = document.createElement('div');
        entry.className = 'log-entry typing-cursor';
        this.container.appendChild(entry);
        
        // Translate backend message if possible
        let translatedMsg = message;
        if (typeof i18n !== 'undefined') {
            translatedMsg = i18n.translateBackendMsg(message);
        }
        
        const fullText = `[${this.getTime()}] ${translatedMsg}`;
        let index = 0;
        // Adjust speed based on length
        const speed = fullText.length > 50 ? 10 : 30;
        
        const type = () => {
            if (index < fullText.length) {
                entry.textContent += fullText.charAt(index);
                index++;
                
                // 自动滚动到底部
                const logSection = document.getElementById('logContainer');
                if (logSection) {
                    logSection.scrollTop = logSection.scrollHeight;
                }
                
                setTimeout(type, speed);
            } else {
                entry.classList.remove('typing-cursor');
            }
        };
        
        type();
        
        // 限制日志数量
        const entries = this.container.querySelectorAll('.log-entry');
        if (entries.length > this.maxEntries) {
            entries[0].remove();
        }
    }
    
    getTime() {
        const now = new Date();
        return now.toLocaleTimeString('zh-CN');
    }
    
    clear() {
        this.container.innerHTML = '';
    }
}

const logger = new Logger('logContent');

/* ===================== API 客户端 ===================== */

class APIClient {
    constructor(baseURL = null) {
        this.baseURL = baseURL || window.location.origin;
        this.statusPoll = null;
    }
    
    async request(endpoint, options = {}) {
        try {
            const url = `${this.baseURL}${endpoint}`;
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };
            
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            
            const response = await fetch(url, {
                headers: headers,
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            logger.log(i18n.t('msg_request_fail') + error.message);
            throw error;
        }
    }
    
    async init() {
        logger.log(i18n.t('msg_init_app'));
        try {
            const result = await this.request('/api/init', { method: 'POST' });
            if (result.success) {
                logger.log(i18n.t('msg_module_loaded'));
            } else {
                logger.log(i18n.t('msg_module_fail') + result.message);
            }
            return result.success;
        } catch (error) {
            logger.log(i18n.t('msg_init_fail'));
            return false;
        }
    }
    
    async getBookInfo(bookId) {
        try {
            const result = await this.request('/api/book-info', {
                method: 'POST',
                body: JSON.stringify({ book_id: bookId })
            });
            
            if (result.success) {
                return result.data;
            } else {
                logger.log(`X ${result.message}`);
                return null;
            }
        } catch (error) {
            logger.log(`X 获取书籍信息失败: ${error.message}`);
            return null;
        }
    }
    
    // ========== 搜索 API ==========
    async searchBooks(keyword, offset = 0) {
        try {
            const result = await this.request('/api/search', {
                method: 'POST',
                body: JSON.stringify({ keyword, offset })
            });
            
            if (result.success) {
                return result.data;
            } else {
                logger.log(`X ${result.message}`);
                return null;
            }
        } catch (error) {
            logger.log(`X 搜索失败: ${error.message}`);
            return null;
        }
    }
    
    async startDownload(bookId, savePath, fileFormat, startChapter, endChapter, selectedChapters) {
        try {
            const body = {
                book_id: bookId,
                save_path: savePath,
                file_format: fileFormat,
                start_chapter: startChapter,
                end_chapter: endChapter
            };
            
            if (selectedChapters && selectedChapters.length > 0) {
                body.selected_chapters = selectedChapters;
            }
            
            const result = await this.request('/api/download', {
                method: 'POST',
                body: JSON.stringify(body)
            });
            
            if (result.success) {
                logger.log(i18n.t('msg_task_started'));
                AppState.setDownloading(true);
                this.startStatusPolling();
                // 自动切换到进度标签页
                switchTab('progress');
                return true;
            } else {
                logger.log(`X ${result.message}`);
                return false;
            }
        } catch (error) {
            logger.log(`X 启动下载失败: ${error.message}`);
            return false;
        }
    }
    
    async cancelDownload() {
        try {
            const result = await this.request('/api/cancel', { method: 'POST' });
            if (result.success) {
                logger.log(i18n.t('msg_download_cancelled'));
                AppState.setDownloading(false);
                this.stopStatusPolling();
                return true;
            }
        } catch (error) {
            logger.log(i18n.t('msg_cancel_fail') + error.message);
        }
        return false;
    }
    
    async getStatus() {
        try {
            return await this.request('/api/status');
        } catch (error) {
            return null;
        }
    }
    
    startStatusPolling() {
        if (this.statusPoll) return;
        
        this.statusPoll = setInterval(async () => {
            const status = await this.getStatus();
            if (status) {
                this.updateUI(status);
                
                // 如果下载完成或被取消，停止轮询
                if (!status.is_downloading) {
                    this.stopStatusPolling();
                    AppState.setDownloading(false);
                }
            }
        }, 500);
    }
    
    stopStatusPolling() {
        if (this.statusPoll) {
            clearInterval(this.statusPoll);
            this.statusPoll = null;
        }
    }
    
    updateUI(status) {
        // 更新进度
        const progress = status.progress || 0;
        const progressFill = document.getElementById('progressFill');
        const progressPercent = document.getElementById('progressPercent');
        
        progressFill.style.width = progress + '%';
        progressPercent.textContent = progress + '%';
        
        // 更新进度标签徽章
        updateProgressBadge(progress);
        
        // 更新消息队列（显示所有消息，不遗漏）
        if (status.messages && status.messages.length > 0) {
            for (const msg of status.messages) {
                logger.log(msg);
            }
        }
        
        // 更新书籍名称
        if (status.book_name) {
            document.getElementById('bookName').textContent = status.book_name;
        }
        
        // 更新状态文本
        if (status.is_downloading) {
            document.getElementById('statusText').textContent = i18n.t('status_downloading');
        } else if (progress === 100) {
            document.getElementById('statusText').textContent = i18n.t('status_completed');
            updateProgressBadge(100); // 清除徽章
        } else {
            document.getElementById('statusText').textContent = i18n.t('status_ready');
        }
    }
    
    async getSavePath() {
        try {
            const result = await this.request('/api/config/save-path');
            return result.path;
        } catch (error) {
            return null;
        }
    }
    
    async setSavePath(path) {
        try {
            const result = await this.request('/api/config/save-path', {
                method: 'POST',
                body: JSON.stringify({ path })
            });
            return result.success;
        } catch (error) {
            return false;
        }
    }
    
    async selectFolder(currentPath = '') {
        try {
            const result = await this.request('/api/select-folder', {
                method: 'POST',
                body: JSON.stringify({ current_path: currentPath })
            });
            return result;
        } catch (error) {
            logger.log(i18n.t('msg_folder_fail') + error.message);
            return { success: false };
        }
    }
    
    // ========== 批量下载 API ==========
    async batchDownload(bookIds, savePath, fileFormat = 'txt') {
        try {
            const result = await this.request('/api/batch-download', {
                method: 'POST',
                body: JSON.stringify({
                    book_ids: bookIds,
                    save_path: savePath,
                    file_format: fileFormat
                })
            });
            return result;
        } catch (error) {
            console.error('批量下载失败:', error);
            return { success: false, message: error.message };
        }
    }
    
    async getBatchStatus() {
        try {
            const result = await this.request('/api/batch-status');
            return result;
        } catch (error) {
            return null;
        }
    }
    
    async cancelBatch() {
        try {
            const result = await this.request('/api/batch-cancel', { method: 'POST' });
            return result.success;
        } catch (error) {
            return false;
        }
    }
    
    async checkUpdate() {
        try {
            const result = await this.request('/api/check-update');
            return result;
        } catch (error) {
            console.error('检查更新失败:', error);
            return { success: false };
        }
    }
    
    async downloadUpdate(url, filename) {
        try {
            const result = await this.request('/api/download-update', {
                method: 'POST',
                body: JSON.stringify({ url, filename })
            });
            return result;
        } catch (error) {
            console.error('启动更新下载失败:', error);
            return { success: false, message: error.message };
        }
    }
    
    async getUpdateStatus() {
        try {
            return await this.request('/api/update-status');
        } catch (error) {
            return null;
        }
    }
    
    async openFolder(path) {
        try {
            await this.request('/api/open-folder', {
                method: 'POST',
                body: JSON.stringify({ path })
            });
        } catch (error) {
            console.error('打开文件夹失败:', error);
        }
    }
}

const api = new APIClient();

/* ===================== 标签页系统 ===================== */

function initTabSystem() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });
}

function switchTab(tabName) {
    // 更新按钮状态
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // 更新内容面板
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.id === `tab-${tabName}`);
    });
}

function updateProgressBadge(progress) {
    const badge = document.getElementById('progressBadge');
    if (AppState.isDownloading && progress < 100) {
        badge.textContent = `${progress}%`;
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

/* ===================== UI 事件处理 ===================== */

function initializeUI() {
    // 初始化标签页系统
    initTabSystem();
    
    // 初始化保存路径
    api.getSavePath().then(path => {
        if (path) {
            AppState.setSavePath(path);
        }
    });
    
    // 下载按钮
    document.getElementById('downloadBtn').addEventListener('click', handleDownload);
    
    // 取消按钮
    document.getElementById('cancelBtn').addEventListener('click', handleCancel);
    
    // 清理按钮
    document.getElementById('clearBtn').addEventListener('click', handleClear);
    
    // 浏览按钮（模拟文件选择）
    document.getElementById('browseBtn').addEventListener('click', handleBrowse);
    
    // 版本信息 - 从API获取
    fetchVersion();
    
    // 初始化章节选择弹窗事件
    initChapterModalEvents();
    
    // 初始化语言切换
    const langBtn = document.getElementById('langToggle');
    if (langBtn) {
        const langLabel = document.getElementById('langLabel');
        
        const updateLangBtn = (lang) => {
            langLabel.textContent = lang === 'zh' ? 'EN' : '中文';
        };
        
        // Initial state
        updateLangBtn(i18n.lang);
        i18n.updatePage();
        
        langBtn.addEventListener('click', () => {
            i18n.toggleLanguage();
        });
        
        i18n.onLanguageChange((lang) => {
            updateLangBtn(lang);
        });
    }
    
    checkForUpdate();
}

// 章节选择相关变量
let currentChapters = [];

function initChapterModalEvents() {
    document.getElementById('chapterModalClose').addEventListener('click', closeChapterModal);
    document.getElementById('cancelChaptersBtn').addEventListener('click', closeChapterModal);
    document.getElementById('confirmChaptersBtn').addEventListener('click', confirmChapterSelection);
    
    document.getElementById('selectAllBtn').addEventListener('click', () => toggleAllChapters(true));
    document.getElementById('selectNoneBtn').addEventListener('click', () => toggleAllChapters(false));
    document.getElementById('selectInvertBtn').addEventListener('click', invertChapterSelection);
    
    // 搜索相关事件
    document.getElementById('searchBtn').addEventListener('click', handleSearch);
    document.getElementById('searchKeyword').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });
    document.getElementById('clearSearchBtn').addEventListener('click', clearSearchResults);
    document.getElementById('loadMoreBtn').addEventListener('click', loadMoreResults);
}

// ========== 搜索功能 ==========
let searchOffset = 0;
let currentSearchKeyword = '';

async function handleSearch() {
    const keyword = document.getElementById('searchKeyword').value.trim();
    if (!keyword) {
        alert('请输入搜索关键词');
        return;
    }
    
    // 重置搜索状态
    searchOffset = 0;
    currentSearchKeyword = keyword;
    
    const searchBtn = document.getElementById('searchBtn');
    searchBtn.disabled = true;
    // searchBtn.textContent = '搜索中...'; // Let's keep icon or just disable
    
    logger.log(`? 正在搜索: ${keyword}`); // TODO: dynamic log for search
    
    const result = await api.searchBooks(keyword, 0);
    
    searchBtn.disabled = false;
    searchBtn.textContent = i18n.t('btn_search');
    
    if (result && result.books) {
        displaySearchResults(result.books, false);
        searchOffset = result.books.length;
        
        // 显示/隐藏加载更多按钮
        const loadMoreContainer = document.getElementById('loadMoreContainer');
        loadMoreContainer.style.display = result.has_more ? 'block' : 'none';
        
        logger.log(`${i18n.t('search_count_prefix')}${result.books.length}${i18n.t('search_count_suffix')}`);
    } else {
        displaySearchResults([], false);
        logger.log('X ' + i18n.t('search_no_results'));
    }
}

async function loadMoreResults() {
    if (!currentSearchKeyword) return;
    
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    loadMoreBtn.disabled = true;
    // loadMoreBtn.textContent = '加载中...';
    
    const result = await api.searchBooks(currentSearchKeyword, searchOffset);
    
    loadMoreBtn.disabled = false;
    loadMoreBtn.textContent = i18n.t('btn_load_more');
    
    if (result && result.books && result.books.length > 0) {
        displaySearchResults(result.books, true);
        searchOffset += result.books.length;
        
        const loadMoreContainer = document.getElementById('loadMoreContainer');
        loadMoreContainer.style.display = result.has_more ? 'block' : 'none';
    } else {
        document.getElementById('loadMoreContainer').style.display = 'none';
    }
}

function displaySearchResults(books, append = false) {
    const headerContainer = document.getElementById('searchHeader');
    const listContainer = document.getElementById('searchResultList');
    const countSpan = document.getElementById('searchResultCount');
    
    headerContainer.style.display = 'flex';
    
    if (!append) {
        listContainer.innerHTML = '';
    }
    
    if (books.length === 0 && !append) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">#</div>
                <div class="empty-state-text">${i18n.t('search_no_results')}</div>
            </div>
        `;
        countSpan.textContent = i18n.t('search_count_prefix') + '0' + i18n.t('search_count_suffix');
        headerContainer.style.display = 'none';
        return;
    }
    
    books.forEach(book => {
        const item = document.createElement('div');
        item.className = 'search-item';
        item.onclick = () => selectBook(book.book_id, book.book_name);
        
        const wordCount = book.word_count ? (book.word_count / 10000).toFixed(1) + '万字' : '';
        const chapterCount = book.chapter_count ? book.chapter_count + '章' : '';
        const status = book.status || '';
        // We might want to translate status too if it's fixed strings
        const statusClass = (status === '完结' || status === '已完结') ? 'complete' : 'ongoing';
        
        item.innerHTML = `
            <img class="search-cover" src="${book.cover_url || ''}" alt="" onerror="this.style.display='none'">
            <div class="search-info">
                <div class="search-title">
                    ${book.book_name}
                    ${status ? `<span class="status-badge ${statusClass}">${status}</span>` : ''}
                </div>
                <div class="search-meta">${book.author} · ${wordCount}${chapterCount ? ' · ' + chapterCount : ''}</div>
                <div class="search-desc">${book.abstract || '暂无简介'}</div>
            </div>
        `;
        
        listContainer.appendChild(item);
    });
    
    // 更新计数
    const totalCount = listContainer.querySelectorAll('.search-item').length;
    countSpan.textContent = `${i18n.t('search_count_prefix')}${totalCount}${i18n.t('search_count_suffix')}`;
}

function selectBook(bookId, bookName) {
    document.getElementById('bookId').value = bookId;
    logger.log(`+ 已选择: ${bookName} (ID: ${bookId})`);
    
    // 自动切换到下载标签页
    switchTab('download');
}

function clearSearchResults() {
    document.getElementById('searchHeader').style.display = 'none';
    document.getElementById('searchResultList').innerHTML = '';
    document.getElementById('searchKeyword').value = '';
    document.getElementById('loadMoreContainer').style.display = 'none';
    searchOffset = 0;
    currentSearchKeyword = '';
}

async function handleSelectChapters() {
    const bookId = document.getElementById('bookId').value.trim();
    if (!bookId) {
        alert('请先输入书籍ID');
        return;
    }
    
    // 验证bookId (简单复用验证逻辑)
    let validId = bookId;
    if (bookId.includes('fanqienovel.com')) {
        const match = bookId.match(/\/page\/(\d+)/);
        if (match) validId = match[1];
        else { alert('URL格式错误'); return; }
    } else if (!/^\d+$/.test(bookId)) {
        alert('书籍ID应为纯数字');
        return;
    }
    
    const modal = document.getElementById('chapterModal');
    const listContainer = document.getElementById('chapterList');
    
    modal.style.display = 'flex';
    listContainer.innerHTML = '<div style="text-align: center; padding: 20px;">正在获取章节列表...</div>';
    
    logger.log(`# 获取章节列表: ${validId}`);
    const bookInfo = await api.getBookInfo(validId);
    
    if (bookInfo && bookInfo.chapters) {
        currentChapters = bookInfo.chapters;
        renderChapterList(bookInfo.chapters);
    } else {
        listContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: red;">获取章节失败</div>';
    }
}

function renderChapterList(chapters) {
    const listContainer = document.getElementById('chapterList');
    listContainer.innerHTML = '';
    
    // 检查是否有已选状态
    const selectedSet = new Set(AppState.selectedChapters || []);
    
    chapters.forEach((ch, idx) => {
        const item = document.createElement('div');
        item.className = 'chapter-item';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.padding = '5px';
        item.style.borderBottom = '1px solid #eee';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = idx;
        checkbox.id = `ch-${idx}`;
        checkbox.checked = selectedSet.has(idx);
        checkbox.addEventListener('change', updateSelectedCount);
        
        const label = document.createElement('label');
        label.htmlFor = `ch-${idx}`;
        label.textContent = `${ch.title}`;
        label.style.marginLeft = '10px';
        label.style.cursor = 'pointer';
        label.style.flex = '1';
        
        item.appendChild(checkbox);
        item.appendChild(label);
        listContainer.appendChild(item);
    });
    
    updateSelectedCount();
}

function updateSelectedCount() {
    const checkboxes = document.querySelectorAll('#chapterList input[type="checkbox"]');
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    document.getElementById('selectedCount').textContent = `已选: ${checked.length} / ${checkboxes.length} 章`;
}

function toggleAllChapters(checked) {
    const checkboxes = document.querySelectorAll('#chapterList input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = checked);
    updateSelectedCount();
}

function invertChapterSelection() {
    const checkboxes = document.querySelectorAll('#chapterList input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = !cb.checked);
    updateSelectedCount();
}

function confirmChapterSelection() {
    const checkboxes = document.querySelectorAll('#chapterList input[type="checkbox"]');
    const selected = Array.from(checkboxes).filter(cb => cb.checked).map(cb => parseInt(cb.value));
    
    AppState.selectedChapters = selected.length > 0 ? selected : null;
    
    const btn = document.getElementById('selectChaptersBtn');
    if (AppState.selectedChapters) {
        btn.textContent = `= 已选 ${AppState.selectedChapters.length} 章`;
        btn.classList.remove('btn-info');
        btn.classList.add('btn-success');
        logger.log(`√ 已确认选择 ${AppState.selectedChapters.length} 个章节`);
    } else {
        btn.textContent = `= 选择章节`;
        btn.classList.remove('btn-success');
        btn.classList.add('btn-info');
        logger.log(`√ 已取消章节选择 (默认下载全部)`);
    }
    
    closeChapterModal();
}

function closeChapterModal() {
    document.getElementById('chapterModal').style.display = 'none';
}

async function checkForUpdate() {
    try {
        const result = await api.checkUpdate();
        
        if (result.success && result.has_update) {
            showUpdateModal(result.data);
        }
    } catch (error) {
        console.error('检查更新失败:', error);
    }
}

function simpleMarkdownToHtml(markdown) {
    if (!markdown) return '暂无更新说明';
    
    let html = markdown;
    
    // 处理 Markdown 表格
    const tableRegex = /\|(.+)\|\n\|([\s\-\:]+\|)+\n((\|.+\|\n?)+)/g;
    html = html.replace(tableRegex, (match) => {
        const lines = match.trim().split('\n');
        if (lines.length < 3) return match;
        
        // 解析表头
        const headerCells = lines[0].split('|').filter(cell => cell.trim());
        // 跳过分隔行 (lines[1])
        // 解析数据行
        const dataRows = lines.slice(2);
        
        let tableHtml = '<table class="md-table"><thead><tr>';
        headerCells.forEach(cell => {
            tableHtml += `<th>${cell.trim()}</th>`;
        });
        tableHtml += '</tr></thead><tbody>';
        
        dataRows.forEach(row => {
            if (row.trim()) {
                const cells = row.split('|').filter(cell => cell.trim() !== '');
                tableHtml += '<tr>';
                cells.forEach(cell => {
                    tableHtml += `<td>${cell.trim()}</td>`;
                });
                tableHtml += '</tr>';
            }
        });
        tableHtml += '</tbody></table>';
        return tableHtml;
    });
    
    // 转换标题
    html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // 转换粗体
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // 转换斜体
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // 转换代码块
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');
    
    // 转换列表
    html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // 转换换行
    html = html.replace(/\n/g, '<br>');
    
    // 清理多余的br标签
    html = html.replace(/<br><h/g, '<h');
    html = html.replace(/<\/h([1-6])><br>/g, '</h$1>');
    html = html.replace(/<br><\/ul>/g, '</ul>');
    html = html.replace(/<ul><br>/g, '<ul>');
    html = html.replace(/<br><table/g, '<table');
    html = html.replace(/<\/table><br>/g, '</table>');
    
    return html;
}

async function showUpdateModal(updateInfo) {
    const modal = document.getElementById('updateModal');
    const currentVersion = document.getElementById('currentVersion');
    const latestVersion = document.getElementById('latestVersion');
    const updateDescription = document.getElementById('updateDescription');
    const versionSelector = document.getElementById('versionSelector');
    const downloadUpdateBtn = document.getElementById('downloadUpdateBtn');
    const closeUpdateBtn = document.getElementById('closeUpdateBtn');
    const updateModalClose = document.getElementById('updateModalClose');
    
    // 重置UI显示状态
    if (updateDescription.parentNode) updateDescription.parentNode.style.display = 'block';
    versionSelector.style.display = 'none';
    downloadUpdateBtn.disabled = false;
    downloadUpdateBtn.textContent = '立即下载';
    
    const modalFooter = document.querySelector('.modal-footer');
    if (modalFooter) modalFooter.style.display = 'flex';
    
    const progressContainer = document.getElementById('updateProgressContainer');
    if (progressContainer) progressContainer.style.display = 'none';
    
    currentVersion.textContent = updateInfo.current_version;
    latestVersion.textContent = updateInfo.latest_version;
    
    const releaseBody = updateInfo.release_info?.body || updateInfo.message || '暂无更新说明';
    updateDescription.innerHTML = simpleMarkdownToHtml(releaseBody);
    
    // 获取可下载的版本选项
    try {
        const response = await fetch('/api/get-update-assets', {
            headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
        });
        const result = await response.json();
        
        if (result.success && result.assets && result.assets.length > 0) {
            // 显示版本选择器
            versionSelector.innerHTML = '<h4>选择下载版本:</h4>';
            const optionsContainer = document.createElement('div');
            optionsContainer.className = 'version-options';
            
            result.assets.forEach((asset, index) => {
                const option = document.createElement('label');
                option.className = 'version-option';
                if (asset.recommended) {
                    option.classList.add('recommended');
                }
                
                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = 'version';
                radio.value = asset.download_url;
                radio.dataset.filename = asset.name;
                if (asset.recommended) {
                    radio.checked = true;
                }
                
                const label = document.createElement('span');
                label.innerHTML = `
                    <strong>${asset.type === 'standalone' ? '完整版' : asset.type === 'debug' ? '调试版' : '标准版'}</strong> 
                    (${asset.size_mb} MB)
                    ${asset.recommended ? '<span class="badge">推荐</span>' : ''}
                    <br>
                    <small>${asset.description}</small>
                `;
                
                option.appendChild(radio);
                option.appendChild(label);
                optionsContainer.appendChild(option);
            });
            
            versionSelector.appendChild(optionsContainer);
            versionSelector.style.display = 'block';
            
            // 检查是否支持自动更新
            let canAutoUpdate = false;
            try {
                const autoUpdateCheck = await fetch('/api/can-auto-update', {
                    headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
                });
                const autoUpdateResult = await autoUpdateCheck.json();
                canAutoUpdate = autoUpdateResult.success && autoUpdateResult.can_auto_update;
                console.log('自动更新检查结果:', autoUpdateResult);
            } catch (e) {
                console.log('无法检查自动更新支持:', e);
            }
            
            // 修改下载按钮逻辑
            downloadUpdateBtn.onclick = async () => {
                const selectedRadio = document.querySelector('input[name="version"]:checked');
                if (!selectedRadio) {
                    alert('请选择一个版本');
                    return;
                }
                
                const downloadUrl = selectedRadio.value;
                const filename = selectedRadio.dataset.filename;
                
                if (canAutoUpdate) {
                    // 自动更新流程 (支持 Windows/Linux/macOS)
                    downloadUpdateBtn.disabled = true;
                    downloadUpdateBtn.textContent = '正在下载...';
                    
                    // 隐藏不需要的元素以腾出空间
                    updateDescription.parentNode.style.display = 'none'; // 隐藏更新说明区域
                    versionSelector.style.display = 'none'; // 隐藏版本选择
                    
                    // 创建或显示进度条
                    let progressContainer = document.getElementById('updateProgressContainer');
                    if (!progressContainer) {
                        progressContainer = document.createElement('div');
                        progressContainer.id = 'updateProgressContainer';
                        progressContainer.innerHTML = `
                            <div style="margin-top: 16px; padding: 12px; background: #0f0f23; border: 2px solid #00ff00; box-shadow: 4px 4px 0 #000000;">
                                <h4 style="margin: 0 0 12px 0; color: #00ff00; text-align: center; font-family: 'Press Start 2P', monospace; font-size: 10px;">> DOWNLOADING_UPDATE...</h4>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-family: 'Press Start 2P', monospace; font-size: 9px;">
                                    <span id="updateProgressText" style="color: #00cc00;">CONNECTING...</span>
                                    <span id="updateProgressPercent" style="color: #00ff00;">0%</span>
                                </div>
                                <div style="background: #1a1a2e; border: 2px solid #006600; height: 16px; position: relative; padding: 2px;">
                                    <div id="updateProgressBar" style="background: #00ff00; height: 100%; width: 0%; transition: width 0.2s steps(4);"></div>
                                </div>
                                <div style="margin-top: 12px; font-size: 10px; color: #008800; text-align: center; font-family: 'Press Start 2P', monospace; line-height: 1.5;">
                                    * DO NOT CLOSE *
                                </div>
                            </div>
                            <button id="installUpdateBtn" style="display: none; margin-top: 16px; width: 100%; padding: 14px; background: #00ff00; color: #000000; border: 2px solid #006600; cursor: pointer; font-size: 12px; font-family: 'Press Start 2P', monospace; box-shadow: 4px 4px 0 #000000;">
                                [ INSTALL & RESTART ]
                            </button>
                        `;
                        // 插入到版本选择器原来的位置（现在隐藏了）
                        versionSelector.parentNode.insertBefore(progressContainer, versionSelector.nextSibling);
                    }
                    progressContainer.style.display = 'block';
                    
                    // 启动下载
                    try {
                        const headers = { 'Content-Type': 'application/json' };
                        if (AppState.accessToken) headers['X-Access-Token'] = AppState.accessToken;
                        
                        const downloadResult = await fetch('/api/download-update', {
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify({ url: downloadUrl, filename: filename })
                        });
                        const downloadData = await downloadResult.json();
                        
                        if (!downloadData.success) {
                            throw new Error(downloadData.message || '启动下载失败');
                        }
                        
                        // 轮询下载进度
                        const pollProgress = async () => {
                            try {
                                const statusRes = await fetch('/api/update-status', {
                                    headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
                                });
                                const status = await statusRes.json();
                                
                                const progressBar = document.getElementById('updateProgressBar');
                                const progressText = document.getElementById('updateProgressText');
                                const progressPercent = document.getElementById('updateProgressPercent');
                                const installBtn = document.getElementById('installUpdateBtn');
                                
                                if (status.is_downloading) {
                                    progressBar.style.width = status.progress + '%';
                                    progressText.textContent = status.message || '正在下载...';
                                    progressPercent.textContent = status.progress + '%';
                                    setTimeout(pollProgress, 500);
                                } else if (status.completed) {
                                    progressBar.style.width = '100%';
                                    progressText.textContent = '√ DOWNLOAD COMPLETE';
                                    progressPercent.textContent = '100%';
                                    
                                    // 隐藏底部按钮区域，避免干扰
                                    const modalFooter = document.querySelector('.modal-footer');
                                    if (modalFooter) modalFooter.style.display = 'none';
                                    
                                    // 显示安装按钮
                                    installBtn.style.display = 'block';
                                    installBtn.onclick = async () => {
                                        installBtn.disabled = true;
                                        installBtn.textContent = '正在准备更新...';
                                        
                                        try {
                                            const applyRes = await fetch('/api/apply-update', { 
                                                method: 'POST',
                                                headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
                                            });
                                            const applyResult = await applyRes.json();
                                            
                                            if (applyResult.success) {
                                                installBtn.textContent = '更新中，程序即将重启...';
                                                progressText.textContent = '* ' + applyResult.message;
                                            } else {
                                                alert('应用更新失败: ' + applyResult.message);
                                                installBtn.disabled = false;
                                                installBtn.textContent = '> 立即安装更新';
                                            }
                                        } catch (e) {
                                            alert('应用更新失败: ' + e.message);
                                            installBtn.disabled = false;
                                            installBtn.textContent = '> 立即安装更新';
                                        }
                                    };
                                } else if (status.error) {
                                    progressText.textContent = 'X ' + status.message;
                                    downloadUpdateBtn.disabled = false;
                                    downloadUpdateBtn.textContent = '重新下载';
                                } else {
                                    // 初始状态，线程可能还未开始，继续轮询
                                    progressText.textContent = '准备下载...';
                                    setTimeout(pollProgress, 500);
                                }
                            } catch (e) {
                                console.error('获取下载状态失败:', e);
                                setTimeout(pollProgress, 1000);
                            }
                        };
                        
                        setTimeout(pollProgress, 500);
                        
                    } catch (e) {
                        alert('下载失败: ' + e.message);
                        downloadUpdateBtn.disabled = false;
                        downloadUpdateBtn.textContent = '下载更新';
                    }
                } else {
                    // 非 Windows 或非自动更新模式，使用浏览器下载
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    link.download = filename;
                    link.style.display = 'none';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    // 同时打开 Release 页面作为备选
                    setTimeout(() => {
                        window.open(result.release_url, '_blank');
                    }, 500);
                    
                    modal.style.display = 'none';
                }
            };
        } else {
            // 如果无法获取 assets,使用默认行为
            versionSelector.style.display = 'none';
            downloadUpdateBtn.onclick = () => {
                window.open(updateInfo.url || updateInfo.release_info?.html_url, '_blank');
                modal.style.display = 'none';
            };
        }
    } catch (error) {
        console.error('获取下载选项失败:', error);
        versionSelector.style.display = 'none';
        downloadUpdateBtn.onclick = () => {
            window.open(updateInfo.url || updateInfo.release_info?.html_url, '_blank');
            modal.style.display = 'none';
        };
    }
    
    modal.style.display = 'flex';
    
    closeUpdateBtn.onclick = () => {
        modal.style.display = 'none';
    };
    
    updateModalClose.onclick = () => {
        modal.style.display = 'none';
    };
    
    modal.onclick = (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    };
}

async function handleDownload() {
    const bookId = document.getElementById('bookId').value.trim();
    const savePath = document.getElementById('savePath').value.trim();
    const fileFormat = document.querySelector('input[name="format"]:checked').value;
    
    if (!bookId) {
        alert('请输入书籍ID或URL');
        return;
    }
    
    if (!savePath) {
        alert('请选择保存路径');
        return;
    }
    
    // 验证bookId格式
    if (bookId.includes('fanqienovel.com')) {
        const match = bookId.match(/\/page\/(\d+)/);
        if (!match) {
            alert('URL格式错误，请使用正确的Fanqie小说URL');
            return;
        }
    } else if (!/^\d+$/.test(bookId)) {
        alert('书籍ID应为纯数字');
        return;
    }
    
    logger.log(`# 正在获取书籍信息: ${bookId}`);
    
    const bookInfo = await api.getBookInfo(bookId);
    if (!bookInfo) {
        alert('获取书籍信息失败，请检查ID是否正确');
        return;
    }
    
    logger.log('√ 获取成功，准备显示确认窗口');
    showConfirmDialog(bookInfo, savePath, fileFormat);
}

function showConfirmDialog(bookInfo, savePath, fileFormat) {
    console.log('showConfirmDialog called with:', bookInfo);
    try {
        const modal = document.createElement('div');
        modal.className = 'modal';
        
        let selectionHtml = '';
    if (AppState.selectedChapters) {
        selectionHtml = `
            <div class="chapter-selection-info" style="padding: 12px; background: #0f0f23; border: 2px solid #00ff00;">
                <p style="margin: 0 0 8px 0; color: #00ff00; font-family: 'Press Start 2P', monospace; font-size: 11px;">√ 已手动选择 ${AppState.selectedChapters.length} 个章节</p>
                <p style="margin: 0 0 10px 0; color: #008800; font-size: 10px;">提示：自定义选择模式下不支持"整书极速下载"</p>
                <button class="btn btn-sm btn-secondary" onclick="window.reSelectChapters()">重新选择章节</button>
            </div>
        `;
    } else {
        selectionHtml = `
            <div class="chapter-range">
                <label>
                    <input type="radio" name="chapterMode" value="all" checked>
                    下载全部章节 (支持极速模式)
                </label>
                <label>
                    <input type="radio" name="chapterMode" value="range">
                    自定义章节范围
                </label>
                <label>
                    <input type="radio" name="chapterMode" value="manual">
                    手动选择章节
                </label>
            </div>
            
            <div class="chapter-inputs" id="chapterInputs" style="display: none;">
                <div class="input-row">
                    <label>起始章节:</label>
                    <select id="startChapter" class="chapter-select">
                        ${bookInfo.chapters.map((ch, idx) => 
                            `<option value="${idx}">${ch.title}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="input-row">
                    <label>结束章节:</label>
                    <select id="endChapter" class="chapter-select">
                        ${bookInfo.chapters.map((ch, idx) => 
                            `<option value="${idx}" ${idx === bookInfo.chapters.length - 1 ? 'selected' : ''}>${ch.title}</option>`
                        ).join('')}
                    </select>
                </div>
            </div>
            
            <div class="chapter-manual-container" id="chapterManualContainer" style="display: none; margin-top: 12px;">
                <div class="chapter-actions" style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 2px solid #006600; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <button class="btn btn-sm btn-secondary" onclick="window.selectAllChaptersInDialog()">全选</button>
                    <button class="btn btn-sm btn-secondary" onclick="window.selectNoneChaptersInDialog()">全不选</button>
                    <button class="btn btn-sm btn-secondary" onclick="window.invertChaptersInDialog()">反选</button>
                    <span id="dialogSelectedCount" style="margin-left: 15px; font-weight: bold;">已选: 0 章</span>
                </div>
                <div class="chapter-list" id="dialogChapterList" style="max-height: 300px; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 8px;">
                    ${bookInfo.chapters.map((ch, idx) => `
                        <label class="chapter-item">
                            <input type="checkbox" value="${idx}" onchange="window.updateDialogSelectedCount()">
                            <span>${ch.title}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
        `;
    }

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>+ 确认下载</h3>
                <button class="modal-close" onclick="this.closest('.modal').remove()">✕</button>
            </div>
            
            <div class="modal-body">
                <div class="book-info">
                    ${bookInfo.cover_url ? `<img src="${bookInfo.cover_url}" alt="封面" class="book-cover" onerror="this.style.display='none'">` : ''}
                    <div class="book-details">
                        <h3 class="book-title">${bookInfo.book_name}</h3>
                        <p class="book-author">作者: ${bookInfo.author}</p>
                        <p class="book-abstract">${bookInfo.abstract}</p>
                        <p class="book-chapters">共 ${bookInfo.chapters.length} 章</p>
                    </div>
                </div>
                
                <div class="chapter-selection">
                    <h3>章节选择</h3>
                    ${selectionHtml}
                </div>
            </div>
            
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">取消</button>
                <button class="btn btn-primary" id="confirmDownloadBtn">开始下载</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Force display flex
    modal.style.display = 'flex';
    
    if (!AppState.selectedChapters) {
        const chapterModeInputs = modal.querySelectorAll('input[name="chapterMode"]');
        const chapterInputs = modal.querySelector('#chapterInputs');
        const chapterManualContainer = modal.querySelector('#chapterManualContainer');
        
        chapterModeInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                chapterInputs.style.display = e.target.value === 'range' ? 'block' : 'none';
                chapterManualContainer.style.display = e.target.value === 'manual' ? 'block' : 'none';
            });
        });
    }
    
    modal.querySelector('#confirmDownloadBtn').addEventListener('click', () => {
        let startChapter = null;
        let endChapter = null;
        let selectedChapters = AppState.selectedChapters;
        
        if (selectedChapters) {
            logger.log(`# 准备下载《${bookInfo.book_name}》`);
            logger.log(`> 模式: 手动选择 (${selectedChapters.length} 章)`);
        } else {
            // Safe check for chapterMode
            const modeInput = modal.querySelector('input[name="chapterMode"]:checked');
            if (!modeInput && !selectedChapters) {
                // Default to all if nothing checked (shouldn't happen due to default checked)
                startChapter = null; endChapter = null;
            } else {
                const mode = modeInput.value;
                if (mode === 'range') {
                    startChapter = parseInt(modal.querySelector('#startChapter').value);
                    endChapter = parseInt(modal.querySelector('#endChapter').value);
                    
                    if (startChapter > endChapter) {
                        alert('起始章节不能大于结束章节');
                        return;
                    }
                    
                    logger.log(`# 准备下载《${bookInfo.book_name}》`);
                    logger.log(`> 章节范围: 第 ${startChapter + 1} 章 - 第 ${endChapter + 1} 章`);
                } else if (mode === 'manual') {
                    // 获取手动选择的章节
                    const checkboxes = modal.querySelectorAll('#dialogChapterList input[type="checkbox"]:checked');
                    selectedChapters = Array.from(checkboxes).map(cb => parseInt(cb.value));
                    
                    if (selectedChapters.length === 0) {
                        alert('请至少选择一个章节');
                        return;
                    }
                    
                    logger.log(`# 准备下载《${bookInfo.book_name}》`);
                    logger.log(`> 模式: 手动选择 (${selectedChapters.length} 章)`);
                } else {
                    logger.log(`# 准备下载《${bookInfo.book_name}》全部章节`);
                }
            }
        }
        
        logger.log(`$ 保存路径: ${savePath}`);
        logger.log(`= 文件格式: ${fileFormat.toUpperCase()}`);
        
        api.startDownload(bookInfo.book_id, savePath, fileFormat, startChapter, endChapter, selectedChapters);
        modal.remove();
    });
    } catch (e) {
        console.error('Error showing confirm dialog:', e);
        logger.log(`X 显示确认窗口失败: ${e.message}`);
        alert('显示确认窗口失败，请查看控制台日志');
    }
}


async function handleCancel() {
    if (confirm('确定要取消下载吗？')) {
        await api.cancelDownload();
    }
}

// 全局辅助函数 - 对话框内的章节选择
window.updateDialogSelectedCount = function() {
    const checkboxes = document.querySelectorAll('#dialogChapterList input[type="checkbox"]');
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const countElement = document.getElementById('dialogSelectedCount');
    if (countElement) {
        countElement.textContent = `已选: ${checked.length} 章`;
    }
};

window.selectAllChaptersInDialog = function() {
    const checkboxes = document.querySelectorAll('#dialogChapterList input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = true);
    window.updateDialogSelectedCount();
};

window.selectNoneChaptersInDialog = function() {
    const checkboxes = document.querySelectorAll('#dialogChapterList input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
    window.updateDialogSelectedCount();
};

window.invertChaptersInDialog = function() {
    const checkboxes = document.querySelectorAll('#dialogChapterList input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = !cb.checked);
    window.updateDialogSelectedCount();
};

window.reSelectChapters = function() {
    // 重置章节选择状态
    AppState.selectedChapters = null;
    // 关闭当前对话框
    const modal = document.querySelector('.modal');
    if (modal) modal.remove();
    // 重新点击下载按钮
    handleDownload();
};

function handleClear() {
    if (confirm('确定要清理所有设置吗？')) {
        document.getElementById('bookId').value = '';
        document.getElementById('savePath').value = '';
        document.querySelector('input[name="format"]').checked = true;
        
        // 重置章节选择
        AppState.selectedChapters = null;
        
        logger.clear();
        logger.log('~ 设置已清理');
    }
}

async function handleBrowse() {
    const currentPath = document.getElementById('savePath').value || '';
    
    logger.log('> 打开文件夹选择对话框...');
    
    const result = await api.selectFolder(currentPath);
    
    if (result.success && result.path) {
        AppState.setSavePath(result.path);
        logger.log(`√ 保存路径已更新: ${result.path}`);
    } else if (result.message && result.message !== '未选择文件夹') {
        logger.log(`X ${result.message}`);
    }
}

/* ===================== 初始化 ===================== */

document.addEventListener('DOMContentLoaded', async () => {
    logger.log(i18n.t('msg_app_start'));
    
    // 从URL获取访问令牌
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
        AppState.setAccessToken(token);
        logger.log(i18n.t('msg_token_loaded'));
    }
    
    initializeUI();
    
    // 初始化模块
    const success = await api.init();
    if (success) {
        logger.log(i18n.t('msg_ready'));
    } else {
        logger.log(i18n.t('msg_init_partial'));
        logger.log(i18n.t('msg_check_network'));
    }
});

/* ===================== 热键支持 ===================== */

document.addEventListener('keydown', (e) => {
    // Ctrl+Enter 快速下载
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const downloadBtn = document.getElementById('downloadBtn');
        if (downloadBtn.style.display !== 'none' && !downloadBtn.disabled) {
            handleDownload();
        }
    }
});
