/* ===================== 全局状态管理 ===================== */

const AppState = {
    isDownloading: false,
    currentProgress: 0,
    savePath: '',
    accessToken: '',
    selectedChapters: null, // 存储选中的章节索引数组
    downloadQueue: [],
    queueStorageKey: 'fanqie_download_queue',
    
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

    loadQueue() {
        try {
            const raw = localStorage.getItem(this.queueStorageKey);
            if (!raw) {
                this.downloadQueue = [];
                return;
            }
            const parsed = JSON.parse(raw);
            this.downloadQueue = Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            this.downloadQueue = [];
        }
    },

    saveQueue() {
        try {
            localStorage.setItem(this.queueStorageKey, JSON.stringify(this.downloadQueue));
        } catch (e) {
            // ignore
        }
    },

    addToQueue(task) {
        this.downloadQueue.push(task);
        this.saveQueue();
        renderQueue();
    },

    removeFromQueue(taskId) {
        this.downloadQueue = this.downloadQueue.filter(t => t && t.id !== taskId);
        this.saveQueue();
        renderQueue();
    },

    clearQueue() {
        this.downloadQueue = [];
        this.saveQueue();
        renderQueue();
    },
    
    updateUIState() {
        const downloadBtn = document.getElementById('downloadBtn');
        const cancelBtn = document.getElementById('cancelBtn');
        const bookIdInput = document.getElementById('bookId');
        const browseBtn = document.getElementById('browseBtn');
        const startQueueBtn = document.getElementById('startQueueBtn');
        const clearQueueBtn = document.getElementById('clearQueueBtn');
        const apiSourceSelect = document.getElementById('apiSourceSelect');
        const refreshApiSourcesBtn = document.getElementById('refreshApiSourcesBtn');
        
        if (this.isDownloading) {
            downloadBtn.style.display = 'none';
            cancelBtn.style.display = 'inline-block';
            bookIdInput.disabled = true;
            browseBtn.disabled = true;
            if (startQueueBtn) startQueueBtn.disabled = true;
            if (clearQueueBtn) clearQueueBtn.disabled = true;
            if (apiSourceSelect) apiSourceSelect.disabled = true;
            if (refreshApiSourcesBtn) refreshApiSourcesBtn.disabled = true;
        } else {
            downloadBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'none';
            bookIdInput.disabled = false;
            browseBtn.disabled = false;
            if (startQueueBtn) startQueueBtn.disabled = false;
            if (clearQueueBtn) clearQueueBtn.disabled = false;
            if (apiSourceSelect) apiSourceSelect.disabled = false;
            if (refreshApiSourcesBtn) refreshApiSourcesBtn.disabled = false;
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
            logger.logKey('msg_version_info', data.version);
        }
    } catch (e) {
        console.error('获取版本信息失败:', e);
        // 重试最多3次
        if (retryCount < 3) {
            setTimeout(() => fetchVersion(retryCount + 1), 1000);
        } else {
            logger.logKey('msg_fetch_version_fail');
        }
    }
}

/* ===================== 日志管理 ===================== */

class Logger {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.maxEntries = 100;
        this.entries = [];
    }
    
    logKey(key, ...args) {
        this._addEntry({
            type: 'key',
            key: key,
            args: args,
            time: this.getTime()
        });
    }
    
    log(message) {
        this._addEntry({
            type: 'raw',
            message: message,
            time: this.getTime()
        });
    }
    
    _addEntry(data) {
        this.entries.push(data);
        if (this.entries.length > this.maxEntries) {
            this.entries.shift();
        }
        
        const entry = document.createElement('div');
        entry.className = 'log-entry typing-cursor';
        this.container.appendChild(entry);
        
        const fullText = `[${data.time}] ${this._formatText(data)}`;
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
        const domEntries = this.container.querySelectorAll('.log-entry');
        if (domEntries.length > this.maxEntries) {
            domEntries[0].remove();
        }
    }
    
    refresh() {
        this.container.innerHTML = '';
        this.entries.forEach(data => {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.textContent = `[${data.time}] ${this._formatText(data)}`;
            this.container.appendChild(entry);
        });
        
        const logSection = document.getElementById('logContainer');
        if (logSection) {
            logSection.scrollTop = logSection.scrollHeight;
        }
    }
    
    _formatText(data) {
        if (data.type === 'key') {
            return (typeof i18n !== 'undefined' ? i18n.t(data.key, ...(data.args || [])) : data.key) + (data.suffix || '');
        } else {
            let msg = data.message;
            if (typeof i18n !== 'undefined') {
                msg = i18n.translateBackendMsg(msg);
            }
            return msg;
        }
    }
    
    getTime() {
        const now = new Date();
        return now.toLocaleTimeString('zh-CN');
    }
    
    clear() {
        this.container.innerHTML = '';
        this.entries = [];
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
            logger.logKey('msg_request_fail', error.message);
            throw error;
        }
    }
    
    async init() {
        logger.logKey('msg_init_app');
        try {
            const result = await this.request('/api/init', { method: 'POST' });
            if (result.success) {
                logger.logKey('msg_module_loaded');
            } else {
                logger.logKey('msg_module_fail', result.message);
            }
            return result.success;
        } catch (error) {
            logger.logKey('msg_init_fail');
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
                logger.logKey('msg_book_info_fail', result.message);
                return null;
            }
        } catch (error) {
            logger.logKey('msg_book_info_fail', error.message);
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
                logger.logKey('msg_search_fail', result.message);
                return null;
            }
        } catch (error) {
            logger.logKey('msg_search_fail', error.message);
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
                logger.logKey('msg_task_started');
                AppState.setDownloading(true);
                this.startStatusPolling();
                return true;
            } else {
                logger.log(result.message);
                return false;
            }
        } catch (error) {
            logger.logKey('msg_start_download_fail', error.message);
            return false;
        }
    }
    
    async cancelDownload() {
        try {
            const result = await this.request('/api/cancel', { method: 'POST' });
            if (result.success) {
                logger.logKey('msg_download_cancelled');
                AppState.setDownloading(false);
                this.stopStatusPolling();
                return true;
            }
        } catch (error) {
            logger.logKey('msg_cancel_fail', error.message);
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
            const queueInfo = status.queue_total ? ` (${status.queue_current || 1}/${status.queue_total})` : '';
            document.getElementById('statusText').innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg> ${i18n.t('status_downloading')}${queueInfo}`;
        } else if (progress === 100) {
            document.getElementById('statusText').innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> ${i18n.t('status_completed')}`;
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
            logger.logKey('msg_folder_fail', error.message);
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

    // ========== 待下载队列 API ==========
    async startQueue(tasks, savePath, fileFormat = 'txt') {
        try {
            const result = await this.request('/api/queue/start', {
                method: 'POST',
                body: JSON.stringify({
                    tasks,
                    save_path: savePath,
                    file_format: fileFormat
                })
            });
            return result;
        } catch (error) {
            console.error('启动队列下载失败:', error);
            return { success: false, message: error.message };
        }
    }

    // ========== 下载接口选择 API ==========
    async getApiSources() {
        try {
            return await this.request('/api/api-sources');
        } catch (error) {
            return { success: false, message: error.message };
        }
    }

    async selectApiSource(mode, baseUrl = '') {
        try {
            return await this.request('/api/api-sources/select', {
                method: 'POST',
                body: JSON.stringify({
                    mode,
                    base_url: baseUrl
                })
            });
        } catch (error) {
            return { success: false, message: error.message };
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

/* ===================== 待下载队列 ===================== */

function formatQueueChapterInfo(task) {
    if (task && Array.isArray(task.selected_chapters) && task.selected_chapters.length > 0) {
        return i18n.t('queue_item_chapters_manual', task.selected_chapters.length);
    }
    if (typeof task?.start_chapter === 'number' && typeof task?.end_chapter === 'number') {
        return i18n.t('queue_item_chapters_range', task.start_chapter, task.end_chapter);
    }
    return i18n.t('queue_item_chapters_all');
}

function renderQueue() {
    const list = document.getElementById('queueList');
    const summary = document.getElementById('queueSummary');
    if (!list || !summary) return;

    const tasks = Array.isArray(AppState.downloadQueue) ? AppState.downloadQueue : [];
    summary.textContent = i18n.t('queue_summary_count', tasks.length);

    if (tasks.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M3 12h18"></path><path d="M3 18h18"></path></svg>
                </div>
                <div class="empty-state-text">${i18n.t('queue_empty')}</div>
            </div>
        `;
        return;
    }

    list.innerHTML = '';
    tasks.forEach(task => {
        if (!task) return;

        const item = document.createElement('div');
        item.className = 'queue-item';

        const title = task.book_name || task.book_id || i18n.t('queue_unknown_book');
        const meta = [
            task.author || '',
            task.book_id ? `ID: ${task.book_id}` : ''
        ].filter(Boolean).join(' · ');

        item.innerHTML = `
            <div class="queue-item-main">
                <div class="queue-item-title">${title}</div>
                <div class="queue-item-meta">${meta}</div>
                <div class="queue-item-meta">${formatQueueChapterInfo(task)}</div>
            </div>
            <div class="queue-item-actions">
                <button class="btn btn-sm btn-text" type="button">${i18n.t('btn_remove_from_queue')}</button>
            </div>
        `;

        const removeBtn = item.querySelector('button');
        removeBtn.addEventListener('click', () => {
            AppState.removeFromQueue(task.id);
            logger.logKey('msg_removed_from_queue', title);
        });

        list.appendChild(item);
    });
}

async function handleStartQueueDownload() {
    if (AppState.isDownloading) {
        alert(i18n.t('alert_download_in_progress'));
        return;
    }

    const tasks = Array.isArray(AppState.downloadQueue) ? AppState.downloadQueue : [];
    if (tasks.length === 0) {
        alert(i18n.t('alert_queue_empty'));
        return;
    }

    const savePath = document.getElementById('savePath').value.trim();
    if (!savePath) {
        alert(i18n.t('alert_select_path'));
        switchTab('download');
        return;
    }

    const fileFormat = document.querySelector('input[name="format"]:checked').value;

    const payload = tasks.map(t => ({
        book_id: t.book_id,
        start_chapter: t.start_chapter,
        end_chapter: t.end_chapter,
        selected_chapters: t.selected_chapters
    }));

    const result = await api.startQueue(payload, savePath, fileFormat);
    if (result && result.success) {
        logger.logKey('msg_queue_started', payload.length);
        AppState.clearQueue();
        AppState.setDownloading(true);
        api.startStatusPolling();
        return;
    }

    const message = result?.message || i18n.t('msg_start_download_fail', '');
    logger.log(message);
    alert(message);
}

function handleClearQueue() {
    const tasks = Array.isArray(AppState.downloadQueue) ? AppState.downloadQueue : [];
    if (tasks.length === 0) return;

    if (!confirm(i18n.t('confirm_clear_queue'))) return;

    AppState.clearQueue();
    logger.logKey('msg_queue_cleared');
}

/* ===================== 下载接口选择 ===================== */

let apiSourcesCache = null;
let apiSourceControlsInitialized = false;

function renderApiSourcesUI(data) {
    const select = document.getElementById('apiSourceSelect');
    const statusEl = document.getElementById('apiSourceStatus');
    if (!select || !statusEl) return;

    apiSourcesCache = data;

    const sources = Array.isArray(data?.sources) ? data.sources : [];
    const mode = data?.mode || 'auto';
    const current = data?.current || '';

    select.innerHTML = '';

    const autoOpt = document.createElement('option');
    autoOpt.value = '__auto__';
    autoOpt.textContent = i18n.t('api_auto_select');
    select.appendChild(autoOpt);

    sources.forEach(src => {
        const opt = document.createElement('option');
        opt.value = src.base_url;

        const name = src.name || src.base_url;
        if (src.available) {
            const ms = typeof src.latency_ms === 'number' ? src.latency_ms : '?';
            opt.textContent = `${name} (${i18n.t('api_available_latency', ms)})`;
        } else {
            opt.textContent = `${name} (${i18n.t('api_unavailable')})`;
        }
        select.appendChild(opt);
    });

    // Select current mode/endpoint
    if (mode === 'auto') {
        select.value = '__auto__';
    } else if (current) {
        select.value = current;
    }

    // Update status text
    const currentSrc = sources.find(s => s.base_url === current);
    statusEl.className = 'helper-text';
    if (!current) {
        statusEl.textContent = i18n.t('api_status_no_current');
        statusEl.classList.add('bad');
        return;
    }

    const currentName = currentSrc?.name || current;
    if (currentSrc?.available) {
        const ms = typeof currentSrc.latency_ms === 'number' ? currentSrc.latency_ms : '?';
        statusEl.textContent = mode === 'auto'
            ? i18n.t('api_status_auto', currentName, ms)
            : i18n.t('api_status_manual', currentName, ms);
        statusEl.classList.add('ok');
    } else {
        statusEl.textContent = mode === 'auto'
            ? i18n.t('api_status_auto_bad', currentName)
            : i18n.t('api_status_manual_bad', currentName);
        statusEl.classList.add('bad');
    }
}

async function refreshApiSourcesUI() {
    const statusEl = document.getElementById('apiSourceStatus');
    if (statusEl) {
        statusEl.className = 'helper-text';
        statusEl.textContent = i18n.t('api_checking_sources');
    }

    const result = await api.getApiSources();
    if (!result || !result.success) {
        if (statusEl) {
            statusEl.classList.add('bad');
            statusEl.textContent = i18n.t('api_check_failed', result?.message || '');
        }
        return;
    }

    renderApiSourcesUI(result);
}

function initApiSourceControls() {
    if (apiSourceControlsInitialized) return;
    apiSourceControlsInitialized = true;

    const select = document.getElementById('apiSourceSelect');
    const refreshBtn = document.getElementById('refreshApiSourcesBtn');
    if (!select || !refreshBtn) return;

    refreshBtn.addEventListener('click', refreshApiSourcesUI);

    select.addEventListener('change', async () => {
        const value = select.value;
        if (value === '__auto__') {
            const res = await api.selectApiSource('auto');
            if (!res.success) {
                alert(res.message || i18n.t('api_select_failed'));
            }
            await refreshApiSourcesUI();
            return;
        }

        const res = await api.selectApiSource('manual', value);
        if (!res.success) {
            alert(res.message || i18n.t('api_select_failed'));
        }
        await refreshApiSourcesUI();
    });

    refreshApiSourcesUI();
}

/* ===================== UI 事件处理 ===================== */

function initializeUI() {
    // 初始化标签页系统
    initTabSystem();

    // 初始化队列
    AppState.loadQueue();
    renderQueue();

    // 初始化下载接口选择
    initApiSourceControls();
    
    // 初始化保存路径
    api.getSavePath().then(path => {
        if (path) {
            AppState.setSavePath(path);
        }
    });
    
    // 下载按钮
    document.getElementById('downloadBtn').addEventListener('click', () => handleAddToQueue());
    
    // 取消按钮
    document.getElementById('cancelBtn').addEventListener('click', handleCancel);
    
    // 清理按钮
    document.getElementById('clearBtn').addEventListener('click', handleClear);
    
    // 浏览按钮（模拟文件选择）
    document.getElementById('browseBtn').addEventListener('click', handleBrowse);

    // 队列按钮
    const startQueueBtn = document.getElementById('startQueueBtn');
    if (startQueueBtn) startQueueBtn.addEventListener('click', handleStartQueueDownload);
    const clearQueueBtn = document.getElementById('clearQueueBtn');
    if (clearQueueBtn) clearQueueBtn.addEventListener('click', handleClearQueue);
    
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
            logger.refresh();
            renderQueue();
            if (apiSourcesCache) renderApiSourcesUI(apiSourcesCache);
        });
    }

    // 初始化风格切换
    const styleBtn = document.getElementById('styleToggle');
    if (styleBtn) {
        const styleLabel = document.getElementById('styleLabel');
        const iconSpan = styleBtn.querySelector('.icon');
        
        // 检查本地存储的风格偏好
        const savedStyle = localStorage.getItem('app_style');
        if (savedStyle === 'scp') {
            document.body.classList.add('scp-mode');
            styleLabel.textContent = 'SCP';
            iconSpan.textContent = '[⚠]';
        }

        styleBtn.addEventListener('click', () => {
            document.body.classList.toggle('scp-mode');
            const isScp = document.body.classList.contains('scp-mode');
            
            styleLabel.textContent = isScp ? 'SCP' : '8-BIT';
            iconSpan.textContent = isScp ? '[⚠]' : '[🎨]';
            
            // 保存偏好
            localStorage.setItem('app_style', isScp ? 'scp' : '8bit');
            
            // 添加切换音效或视觉反馈（可选）
            logger.logKey(isScp ? 'log_scp_access' : 'log_scp_revert');
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
        alert(i18n.t('alert_input_keyword'));
        return;
    }
    
    // 重置搜索状态
    searchOffset = 0;
    currentSearchKeyword = keyword;
    
    const searchBtn = document.getElementById('searchBtn');
    searchBtn.disabled = true;
    // searchBtn.textContent = '搜索中...'; // Let's keep icon or just disable
    
    logger.logKey('msg_searching', keyword);
    
    const result = await api.searchBooks(keyword, 0);
    
    searchBtn.disabled = false;
    searchBtn.textContent = i18n.t('btn_search');
    
    if (result && result.books) {
        displaySearchResults(result.books, false);
        searchOffset = result.books.length;
        
        // 显示/隐藏加载更多按钮
        const loadMoreContainer = document.getElementById('loadMoreContainer');
        loadMoreContainer.style.display = result.has_more ? 'block' : 'none';
        
        logger.logKey('log_search_success', result.books.length);
    } else {
        displaySearchResults([], false);
        logger.logKey('log_search_no_results_x');
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
                <div class="empty-state-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                </div>
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
        
        const wordCount = book.word_count ? (book.word_count / 10000).toFixed(1) + i18n.t('meta_word_count_suffix') : '';
        const chapterCount = book.chapter_count ? book.chapter_count + i18n.t('meta_chapter_count_suffix') : '';
        const status = book.status || '';
        
        // Translate status
        let displayStatus = status;
        let statusClass = 'ongoing';
        
        if (status === '完结' || status === '已完结') {
            displayStatus = i18n.t('status_complete');
            statusClass = 'complete';
        } else if (status === '连载' || status === '连载中') {
            displayStatus = i18n.t('status_ongoing');
        }
        
        item.innerHTML = `
            <img class="search-cover" src="${book.cover_url || ''}" alt="" onerror="this.style.display='none'">
            <div class="search-info">
                <div class="search-title">
                    ${book.book_name}
                    ${status ? `<span class="status-badge ${statusClass}">${displayStatus}</span>` : ''}
                </div>
                <div class="search-meta">${book.author} · ${wordCount}${chapterCount ? ' · ' + chapterCount : ''}</div>
                <div class="search-desc">${book.abstract || i18n.t('label_no_desc')}</div>
            </div>
            <div class="search-actions">
                <button class="btn btn-sm btn-primary" type="button">${i18n.t('btn_add_to_queue')}</button>
            </div>
        `;
        
        const addBtn = item.querySelector('.search-actions button');
        if (addBtn) {
            addBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                handleAddToQueue(book.book_id, {
                    book_name: book.book_name,
                    author: book.author,
                    abstract: book.abstract,
                    cover_url: book.cover_url,
                    chapter_count: book.chapter_count
                });
            });
        }
        
        listContainer.appendChild(item);
    });
    
    // 更新计数
    const totalCount = listContainer.querySelectorAll('.search-item').length;
    countSpan.textContent = `${i18n.t('search_count_prefix')}${totalCount}${i18n.t('search_count_suffix')}`;
}

function selectBook(bookId, bookName) {
    document.getElementById('bookId').value = bookId;
    logger.logKey('log_selected', bookName, bookId);
    
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
        alert(i18n.t('alert_input_book_id'));
        return;
    }
    
    // 验证bookId (简单复用验证逻辑)
    let validId = bookId;
    if (bookId.includes('fanqienovel.com')) {
        const match = bookId.match(/\/page\/(\d+)/);
        if (match) validId = match[1];
        else { alert(i18n.t('alert_url_format_error')); return; }
    } else if (!/^\d+$/.test(bookId)) {
        alert(i18n.t('alert_id_number'));
        return;
    }
    
    const modal = document.getElementById('chapterModal');
    const listContainer = document.getElementById('chapterList');
    
    modal.style.display = 'flex';
    listContainer.innerHTML = `<div style="text-align: center; padding: 20px;">${i18n.t('text_fetching_chapters')}</div>`;
    
    logger.logKey('log_get_chapter_list', validId);
    const bookInfo = await api.getBookInfo(validId);
    
    if (bookInfo && bookInfo.chapters) {
        currentChapters = bookInfo.chapters;
        renderChapterList(bookInfo.chapters);
    } else {
        listContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: red;">${i18n.t('text_fetch_chapter_fail')}</div>`;
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
    document.getElementById('selectedCount').textContent = i18n.t('label_selected_count', checked.length, checkboxes.length);
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
    if (btn) { // check existence as it might not be there in all versions
        if (AppState.selectedChapters) {
            btn.textContent = i18n.t('btn_selected_count', AppState.selectedChapters.length);
            btn.classList.remove('btn-info');
            btn.classList.add('btn-success');
            logger.logKey('log_confirmed_selection', AppState.selectedChapters.length);
        } else {
            btn.textContent = i18n.t('btn_select_chapters');
            btn.classList.remove('btn-success');
            btn.classList.add('btn-info');
            logger.logKey('log_cancel_selection');
        }
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
    if (!markdown) return i18n.t('text_no_changelog');
    
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
    downloadUpdateBtn.textContent = i18n.t('btn_download_update');
    
    const modalFooter = document.querySelector('.modal-footer');
    if (modalFooter) modalFooter.style.display = 'flex';
    
    const progressContainer = document.getElementById('updateProgressContainer');
    if (progressContainer) progressContainer.style.display = 'none';
    
    currentVersion.textContent = updateInfo.current_version;
    latestVersion.textContent = updateInfo.latest_version;
    
    const releaseBody = updateInfo.release_info?.body || updateInfo.message || i18n.t('text_no_changelog');
    updateDescription.innerHTML = simpleMarkdownToHtml(releaseBody);
    
    // 获取可下载的版本选项
    try {
        const response = await fetch('/api/get-update-assets', {
            headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
        });
        const result = await response.json();
        
        if (result.success && result.assets && result.assets.length > 0) {
            // 显示版本选择器
            versionSelector.innerHTML = `<h4>${i18n.t('update_select_version')}</h4>`;
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
                
                let typeText = i18n.t('update_type_standard');
                if (asset.type === 'standalone') typeText = i18n.t('update_type_standalone');
                else if (asset.type === 'debug') typeText = i18n.t('update_type_debug');
                
                const label = document.createElement('span');
                label.innerHTML = `
                    <strong>${typeText}</strong> 
                    (${asset.size_mb} MB)
                    ${asset.recommended ? `<span class="badge">${i18n.t('update_badge_rec')}</span>` : ''}
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
                    alert(i18n.t('alert_select_version'));
                    return;
                }
                
                const downloadUrl = selectedRadio.value;
                const filename = selectedRadio.dataset.filename;
                
                if (canAutoUpdate) {
                    // 自动更新流程 (支持 Windows/Linux/macOS)
                    downloadUpdateBtn.disabled = true;
                    downloadUpdateBtn.textContent = i18n.t('update_btn_downloading');
                    
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
                                <h4 style="margin: 0 0 12px 0; color: #00ff00; text-align: center; font-family: 'Press Start 2P', monospace; font-size: 10px;">${i18n.t('update_progress_title')}</h4>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-family: 'Press Start 2P', monospace; font-size: 9px;">
                                    <span id="updateProgressText" style="color: #00cc00;">${i18n.t('update_status_connecting')}</span>
                                    <span id="updateProgressPercent" style="color: #00ff00;">0%</span>
                                </div>
                                <div style="background: #1a1a2e; border: 2px solid #006600; height: 16px; position: relative; padding: 2px;">
                                    <div id="updateProgressBar" style="background: #00ff00; height: 100%; width: 0%; transition: width 0.2s steps(4);"></div>
                                </div>
                                <div style="margin-top: 12px; font-size: 10px; color: #008800; text-align: center; font-family: 'Press Start 2P', monospace; line-height: 1.5;">
                                    ${i18n.t('update_warn_dont_close')}
                                </div>
                            </div>
                            <button id="installUpdateBtn" style="display: none; margin-top: 16px; width: 100%; padding: 14px; background: #00ff00; color: #000000; border: 2px solid #006600; cursor: pointer; font-size: 12px; font-family: 'Press Start 2P', monospace; box-shadow: 4px 4px 0 #000000;">
                                ${i18n.t('update_btn_install')}
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
                                    progressText.textContent = status.message || i18n.t('update_btn_downloading');
                                    progressPercent.textContent = status.progress + '%';
                                    setTimeout(pollProgress, 500);
                                } else if (status.completed) {
                                    progressBar.style.width = '100%';
                                    progressText.textContent = i18n.t('update_status_complete');
                                    progressPercent.textContent = '100%';
                                    
                                    // 隐藏底部按钮区域，避免干扰
                                    const modalFooter = document.querySelector('.modal-footer');
                                    if (modalFooter) modalFooter.style.display = 'none';
                                    
                                    // 显示安装按钮
                                    installBtn.style.display = 'block';
                                    installBtn.onclick = async () => {
                                        installBtn.disabled = true;
                                        installBtn.textContent = i18n.t('update_btn_preparing');
                                        
                                        try {
                                            const applyRes = await fetch('/api/apply-update', { 
                                                method: 'POST',
                                                headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
                                            });
                                            const applyResult = await applyRes.json();
                                            
                                            if (applyResult.success) {
                                                installBtn.textContent = i18n.t('update_btn_restarting');
                                                progressText.textContent = applyResult.message;
                                            } else {
                                                alert(i18n.t('alert_apply_update_fail') + applyResult.message);
                                                installBtn.disabled = false;
                                                installBtn.textContent = i18n.t('update_btn_install');
                                            }
                                        } catch (e) {
                                            alert(i18n.t('alert_apply_update_fail') + e.message);
                                            installBtn.disabled = false;
                                            installBtn.textContent = i18n.t('update_btn_install');
                                        }
                                    };
                                } else if (status.error) {
                                    progressText.textContent = status.message;
                                    downloadUpdateBtn.disabled = false;
                                    downloadUpdateBtn.textContent = i18n.t('update_btn_retry');
                                } else {
                                    // 初始状态，线程可能还未开始，继续轮询
                                    progressText.textContent = i18n.t('update_status_ready');
                                    setTimeout(pollProgress, 500);
                                }
                            } catch (e) {
                                console.error('获取下载状态失败:', e);
                                setTimeout(pollProgress, 1000);
                            }
                        };
                        
                        setTimeout(pollProgress, 500);
                        
                    } catch (e) {
                        alert(i18n.t('alert_download_fail') + e.message);
                        downloadUpdateBtn.disabled = false;
                        downloadUpdateBtn.textContent = i18n.t('update_btn_default');
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

async function handleAddToQueue(bookIdOverride = null, prefill = null) {
    const bookId = (bookIdOverride ?? document.getElementById('bookId').value).trim();

    if (!bookId) {
        alert(i18n.t('alert_input_book_id'));
        return;
    }

    // 验证 bookId 格式并标准化为纯数字 ID
    let normalizedId = bookId;
    if (bookId.includes('fanqienovel.com')) {
        const match = bookId.match(/\/page\/(\d+)/);
        if (!match) {
            alert(i18n.t('alert_url_error'));
            return;
        }
        normalizedId = match[1];
    } else if (!/^\d+$/.test(bookId)) {
        alert(i18n.t('alert_id_number'));
        return;
    }

    logger.logKey('log_prepare_download', normalizedId);
    showConfirmDialog(normalizedId, prefill);
}

function showConfirmDialog(bookId, prefill = null) {
    try {
        const modal = document.createElement('div');
        modal.className = 'modal';

        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${i18n.t('title_confirm_download')}</h3>
                    <button class="modal-close" type="button" aria-label="Close">×</button>
                </div>

                <div class="modal-body">
                    <div class="book-info">
                        <img id="dialogCover" class="book-cover" alt="封面" style="display:none;" />
                        <div class="book-details">
                            <h3 class="book-title" id="dialogBookTitle"></h3>
                            <p class="book-author" id="dialogBookAuthor"></p>
                            <p class="book-abstract" id="dialogBookAbstract"></p>
                            <p class="book-chapters" id="dialogBookChapters"></p>
                        </div>
                    </div>

                    <div class="chapter-selection">
                        <h3>${i18n.t('title_chapter_selection')}</h3>

                        <div class="chapter-range">
                            <label>
                                <input type="radio" name="chapterMode" value="all" checked>
                                ${i18n.t('radio_all_chapters')}
                            </label>
                            <label>
                                <input type="radio" name="chapterMode" value="range">
                                ${i18n.t('radio_range_chapters')}
                            </label>
                            <label>
                                <input type="radio" name="chapterMode" value="manual">
                                ${i18n.t('radio_manual_chapters')}
                            </label>
                        </div>

                        <div class="chapter-loading-hint" id="chapterLoadingHint" style="display:none;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
                            <span id="chapterLoadingText"></span>
                        </div>

                        <div class="chapter-inputs" id="chapterInputs" style="display:none;">
                            <div class="input-row">
                                <label>${i18n.t('label_start_chapter')}</label>
                                <select id="startChapter" class="chapter-select" disabled></select>
                            </div>
                            <div class="input-row">
                                <label>${i18n.t('label_end_chapter')}</label>
                                <select id="endChapter" class="chapter-select" disabled></select>
                            </div>
                        </div>

                        <div class="chapter-manual-container" id="chapterManualContainer" style="display:none;">
                            <div class="chapter-actions">
                                <button class="btn btn-sm btn-secondary" type="button" id="dialogSelectAllBtn">${i18n.t('btn_select_all')}</button>
                                <button class="btn btn-sm btn-secondary" type="button" id="dialogSelectNoneBtn">${i18n.t('btn_select_none')}</button>
                                <button class="btn btn-sm btn-secondary" type="button" id="dialogSelectInvertBtn">${i18n.t('btn_invert_selection')}</button>
                                <span id="dialogSelectedCount" style="margin-left: auto; font-size: 13px; color: var(--text-secondary);">${i18n.t('label_dialog_selected', 0)}</span>
                            </div>
                            <div class="chapter-list" id="dialogChapterList"></div>
                        </div>
                    </div>
                </div>

                <div class="modal-footer">
                    <button class="btn btn-secondary" type="button" id="dialogCancelBtn">${i18n.t('btn_cancel')}</button>
                    <button class="btn btn-primary" type="button" id="confirmAddQueueBtn">${i18n.t('btn_confirm_add_to_queue')}</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.style.display = 'flex';

        const close = () => modal.remove();

        // Close controls
        modal.querySelector('.modal-close').addEventListener('click', close);
        modal.querySelector('#dialogCancelBtn').addEventListener('click', close);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) close();
        });

        // Elements
        const coverEl = modal.querySelector('#dialogCover');
        const titleEl = modal.querySelector('#dialogBookTitle');
        const authorEl = modal.querySelector('#dialogBookAuthor');
        const abstractEl = modal.querySelector('#dialogBookAbstract');
        const chaptersEl = modal.querySelector('#dialogBookChapters');

        const loadingHint = modal.querySelector('#chapterLoadingHint');
        const loadingText = modal.querySelector('#chapterLoadingText');

        const chapterInputs = modal.querySelector('#chapterInputs');
        const startSelect = modal.querySelector('#startChapter');
        const endSelect = modal.querySelector('#endChapter');

        const manualContainer = modal.querySelector('#chapterManualContainer');
        const manualList = modal.querySelector('#dialogChapterList');
        const selectedCountEl = modal.querySelector('#dialogSelectedCount');

        const confirmBtn = modal.querySelector('#confirmAddQueueBtn');

        const state = {
            loading: true,
            error: null,
            bookInfo: null,
            chapters: []
        };

        // Prefill (search results / user input)
        const preTitle = prefill?.book_name || bookId;
        const preAuthor = prefill?.author ? `${i18n.t('text_author')}${prefill.author}` : i18n.t('text_fetching_book_info');
        titleEl.textContent = preTitle;
        authorEl.textContent = preAuthor;
        abstractEl.textContent = prefill?.abstract || '';
        chaptersEl.textContent = prefill?.chapter_count ? i18n.t('label_total_chapters', prefill.chapter_count) : '';

        const coverUrl = prefill?.cover_url || '';
        if (coverUrl) {
            coverEl.src = coverUrl;
            coverEl.style.display = '';
            coverEl.onerror = () => { coverEl.style.display = 'none'; };
        }

        const getMode = () => modal.querySelector('input[name="chapterMode"]:checked')?.value || 'all';

        const setHint = (text, showSpinner = true) => {
            if (!text) {
                loadingHint.style.display = 'none';
                return;
            }
            loadingHint.style.display = 'flex';
            loadingText.textContent = text;
            loadingHint.classList.toggle('is-error', !showSpinner);
            loadingHint.querySelector('svg').style.display = showSpinner ? 'inline-block' : 'none';
        };

        const updateSelectedCount = () => {
            const checked = manualList.querySelectorAll('input[type=\"checkbox\"]:checked').length;
            selectedCountEl.textContent = i18n.t('label_dialog_selected', checked);
        };

        const renderChaptersControls = () => {
            const chapters = state.chapters || [];

            // Range selects
            startSelect.innerHTML = '';
            endSelect.innerHTML = '';
            chapters.forEach((ch, idx) => {
                const opt1 = document.createElement('option');
                opt1.value = String(idx);
                opt1.textContent = ch.title || `${idx + 1}`;
                startSelect.appendChild(opt1);

                const opt2 = document.createElement('option');
                opt2.value = String(idx);
                opt2.textContent = ch.title || `${idx + 1}`;
                if (idx === chapters.length - 1) opt2.selected = true;
                endSelect.appendChild(opt2);
            });
            startSelect.disabled = chapters.length === 0;
            endSelect.disabled = chapters.length === 0;

            // Manual list
            manualList.innerHTML = '';
            chapters.forEach((ch, idx) => {
                const label = document.createElement('label');
                label.className = 'chapter-item';
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.value = String(idx);
                checkbox.addEventListener('change', updateSelectedCount);

                const span = document.createElement('span');
                span.textContent = ch.title || `${idx + 1}`;

                label.appendChild(checkbox);
                label.appendChild(span);
                manualList.appendChild(label);
            });
            updateSelectedCount();
        };

        const showLoadingChapters = () => {
            startSelect.disabled = true;
            endSelect.disabled = true;
            startSelect.innerHTML = '';
            endSelect.innerHTML = '';
            manualList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-text">${i18n.t('text_fetching_chapters')}</div>
                </div>
            `;
            selectedCountEl.textContent = i18n.t('label_dialog_selected', 0);
        };

        const updateModeUI = () => {
            const mode = getMode();
            chapterInputs.style.display = mode === 'range' ? 'grid' : 'none';
            manualContainer.style.display = mode === 'manual' ? 'block' : 'none';

            if (mode === 'all') {
                setHint('');
                confirmBtn.disabled = false;
                return;
            }

            if (state.loading) {
                setHint(i18n.t('text_fetching_chapters'), true);
                showLoadingChapters();
                confirmBtn.disabled = true;
                return;
            }

            if (state.error) {
                setHint(state.error, false);
                confirmBtn.disabled = true;
                return;
            }

            setHint('');
            confirmBtn.disabled = false;
        };

        // Mode change handlers
        modal.querySelectorAll('input[name=\"chapterMode\"]').forEach(input => {
            input.addEventListener('change', updateModeUI);
        });

        // Manual action buttons
        modal.querySelector('#dialogSelectAllBtn').addEventListener('click', () => {
            manualList.querySelectorAll('input[type=\"checkbox\"]').forEach(cb => cb.checked = true);
            updateSelectedCount();
        });
        modal.querySelector('#dialogSelectNoneBtn').addEventListener('click', () => {
            manualList.querySelectorAll('input[type=\"checkbox\"]').forEach(cb => cb.checked = false);
            updateSelectedCount();
        });
        modal.querySelector('#dialogSelectInvertBtn').addEventListener('click', () => {
            manualList.querySelectorAll('input[type=\"checkbox\"]').forEach(cb => cb.checked = !cb.checked);
            updateSelectedCount();
        });

        // Confirm
        confirmBtn.addEventListener('click', () => {
            const mode = getMode();

            let startChapter = null;
            let endChapter = null;
            let selectedChapters = null;

            if (mode === 'range') {
                if (state.loading) {
                    updateModeUI();
                    return;
                }
                const startIdx = parseInt(startSelect.value, 10);
                const endIdx = parseInt(endSelect.value, 10);
                if (Number.isNaN(startIdx) || Number.isNaN(endIdx) || startIdx > endIdx) {
                    alert(i18n.t('alert_chapter_range_error'));
                    return;
                }
                startChapter = startIdx + 1;
                endChapter = endIdx + 1;
                logger.logKey('log_chapter_range', startChapter, endChapter);
            } else if (mode === 'manual') {
                if (state.loading) {
                    updateModeUI();
                    return;
                }
                selectedChapters = Array.from(manualList.querySelectorAll('input[type=\"checkbox\"]:checked'))
                    .map(cb => parseInt(cb.value, 10))
                    .filter(n => !Number.isNaN(n));

                if (selectedChapters.length === 0) {
                    alert(i18n.t('alert_select_one_chapter'));
                    return;
                }
                logger.logKey('log_mode_manual', selectedChapters.length);
            } else {
                logger.logKey('log_download_all', preTitle);
            }

            const info = state.bookInfo;
            const task = {
                id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
                book_id: info?.book_id || bookId,
                book_name: info?.book_name || preTitle,
                author: info?.author || prefill?.author || '',
                cover_url: info?.cover_url || prefill?.cover_url || '',
                abstract: info?.abstract || prefill?.abstract || '',
                chapter_count: (info?.chapters?.length || prefill?.chapter_count || 0),
                start_chapter: startChapter,
                end_chapter: endChapter,
                selected_chapters: selectedChapters,
                added_at: new Date().toISOString()
            };

            AppState.addToQueue(task);
            logger.logKey('msg_added_to_queue', task.book_name || task.book_id);
            close();
            switchTab('queue');
        });

        // Initial mode UI
        updateModeUI();

        // Start fetching book info & chapters after modal is shown
        (async () => {
            showLoadingChapters();
            try {
                const info = await api.getBookInfo(bookId);
                if (!info) {
                    state.loading = false;
                    state.error = i18n.t('text_fetch_chapter_fail');
                    updateModeUI();
                    return;
                }

                state.bookInfo = info;
                state.chapters = Array.isArray(info.chapters) ? info.chapters : [];
                state.loading = false;
                state.error = null;

                // Update book info block
                titleEl.textContent = info.book_name || preTitle;
                authorEl.textContent = `${i18n.t('text_author')}${info.author || prefill?.author || ''}`;
                abstractEl.textContent = info.abstract || prefill?.abstract || '';
                chaptersEl.textContent = i18n.t('label_total_chapters', state.chapters.length);

                if (info.cover_url) {
                    coverEl.src = info.cover_url;
                    coverEl.style.display = '';
                    coverEl.onerror = () => { coverEl.style.display = 'none'; };
                }

                renderChaptersControls();
                updateModeUI();
            } catch (e) {
                state.loading = false;
                state.error = e?.message || i18n.t('text_fetch_chapter_fail');
                updateModeUI();
            }
        })();
    } catch (e) {
        console.error('Error showing confirm dialog:', e);
        logger.logKey('log_show_dialog_fail', e.message);
        alert(i18n.t('alert_show_dialog_fail'));
    }
}

function showConfirmDialogLegacy(bookInfo) {
    console.log('showConfirmDialog called with:', bookInfo);
    try {
        const modal = document.createElement('div');
        modal.className = 'modal';
        
        let selectionHtml = '';
    if (AppState.selectedChapters) {
        selectionHtml = `
            <div class="chapter-selection-info" style="padding: 12px; background: #0f0f23; border: 2px solid #00ff00;">
                <p style="margin: 0 0 8px 0; color: #00ff00; font-family: 'Press Start 2P', monospace; font-size: 11px;">${i18n.t('label_manual_selected', AppState.selectedChapters.length)}</p>
                <p style="margin: 0 0 10px 0; color: #008800; font-size: 10px;">${i18n.t('hint_manual_mode')}</p>
                <button class="btn btn-sm btn-secondary" onclick="window.reSelectChapters()">${i18n.t('btn_reselect')}</button>
            </div>
        `;
    } else {
        selectionHtml = `
            <div class="chapter-range">
                <label>
                    <input type="radio" name="chapterMode" value="all" checked>
                    ${i18n.t('radio_all_chapters')}
                </label>
                <label>
                    <input type="radio" name="chapterMode" value="range">
                    ${i18n.t('radio_range_chapters')}
                </label>
                <label>
                    <input type="radio" name="chapterMode" value="manual">
                    ${i18n.t('radio_manual_chapters')}
                </label>
            </div>
            
            <div class="chapter-inputs" id="chapterInputs" style="display: none;">
                <div class="input-row">
                    <label>${i18n.t('label_start_chapter')}</label>
                    <select id="startChapter" class="chapter-select">
                        ${bookInfo.chapters.map((ch, idx) => 
                            `<option value="${idx}">${ch.title}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="input-row">
                    <label>${i18n.t('label_end_chapter')}</label>
                    <select id="endChapter" class="chapter-select">
                        ${bookInfo.chapters.map((ch, idx) => 
                            `<option value="${idx}" ${idx === bookInfo.chapters.length - 1 ? 'selected' : ''}>${ch.title}</option>`
                        ).join('')}
                    </select>
                </div>
            </div>
            
            <div class="chapter-manual-container" id="chapterManualContainer" style="display: none; margin-top: 12px;">
                <div class="chapter-actions" style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 2px solid #006600; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <button class="btn btn-sm btn-secondary" onclick="window.selectAllChaptersInDialog()">${i18n.t('btn_select_all')}</button>
                    <button class="btn btn-sm btn-secondary" onclick="window.selectNoneChaptersInDialog()">${i18n.t('btn_select_none')}</button>
                    <button class="btn btn-sm btn-secondary" onclick="window.invertChaptersInDialog()">${i18n.t('btn_invert_selection')}</button>
                    <span id="dialogSelectedCount" style="margin-left: 15px; font-weight: bold;">${i18n.t('label_dialog_selected', 0)}</span>
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
                <h3>${i18n.t('title_confirm_download')}</h3>
                <button class="modal-close" onclick="this.closest('.modal').remove()">×</button>
            </div>
            
            <div class="modal-body">
                <div class="book-info">
                    ${bookInfo.cover_url ? `<img src="${bookInfo.cover_url}" alt="封面" class="book-cover" onerror="this.style.display='none'">` : ''}
                    <div class="book-details">
                        <h3 class="book-title">${bookInfo.book_name}</h3>
                        <p class="book-author">${i18n.t('text_author')}${bookInfo.author}</p>
                        <p class="book-abstract">${bookInfo.abstract}</p>
                        <p class="book-chapters">${i18n.t('label_total_chapters', bookInfo.chapters.length)}</p>
                    </div>
                </div>
                
                <div class="chapter-selection">
                    <h3>${i18n.t('title_chapter_selection')}</h3>
                    ${selectionHtml}
                </div>
            </div>
            
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">${i18n.t('btn_cancel')}</button>
                <button class="btn btn-primary" id="confirmDownloadBtn">${i18n.t('btn_confirm_add_to_queue')}</button>
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
            logger.logKey('log_prepare_download', bookInfo.book_name);
            logger.logKey('log_mode_manual', selectedChapters.length);
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
                        alert(i18n.t('alert_chapter_range_error'));
                        return;
                    }

                    // 章节范围使用 1-based（end 为包含）
                    startChapter = startChapter + 1;
                    endChapter = endChapter + 1;
                    
                    logger.logKey('log_prepare_download', bookInfo.book_name);
                    logger.logKey('log_chapter_range', startChapter, endChapter);
                } else if (mode === 'manual') {
                    // 获取手动选择的章节
                    const checkboxes = modal.querySelectorAll('#dialogChapterList input[type="checkbox"]:checked');
                    selectedChapters = Array.from(checkboxes).map(cb => parseInt(cb.value));
                    
                    if (selectedChapters.length === 0) {
                        alert(i18n.t('alert_select_one_chapter'));
                        return;
                    }
                    
                    logger.logKey('log_prepare_download', bookInfo.book_name);
                    logger.logKey('log_mode_manual', selectedChapters.length);
                } else {
                    logger.logKey('log_download_all', bookInfo.book_name);
                }
            }
        }
        
        const task = {
            id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
            book_id: bookInfo.book_id,
            book_name: bookInfo.book_name,
            author: bookInfo.author,
            cover_url: bookInfo.cover_url,
            abstract: bookInfo.abstract,
            chapter_count: bookInfo.chapters?.length || 0,
            start_chapter: startChapter,
            end_chapter: endChapter,
            selected_chapters: selectedChapters,
            added_at: new Date().toISOString()
        };

        AppState.addToQueue(task);
        logger.logKey('msg_added_to_queue', bookInfo.book_name);
        modal.remove();
        switchTab('queue');
    });
    } catch (e) {
        console.error('Error showing confirm dialog:', e);
        logger.logKey('log_show_dialog_fail', e.message);
        alert(i18n.t('alert_show_dialog_fail'));
    }
}


async function handleCancel() {
    if (confirm(i18n.t('confirm_cancel_download'))) {
        await api.cancelDownload();
    }
}

// 全局辅助函数 - 对话框内的章节选择
window.updateDialogSelectedCount = function() {
    const checkboxes = document.querySelectorAll('#dialogChapterList input[type="checkbox"]');
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const countElement = document.getElementById('dialogSelectedCount');
    if (countElement) {
        countElement.textContent = i18n.t('label_dialog_selected', checked.length);
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
    handleAddToQueue();
};

function handleClear() {
    if (confirm(i18n.t('confirm_clear_settings'))) {
        document.getElementById('bookId').value = '';
        document.getElementById('savePath').value = '';
        document.querySelector('input[name="format"]').checked = true;
        
        // 重置章节选择
        AppState.selectedChapters = null;
        
        logger.clear();
        logger.logKey('msg_settings_cleared');
    }
}

async function handleBrowse() {
    const currentPath = document.getElementById('savePath').value || '';
    
    logger.logKey('msg_open_folder_dialog');
    
    const result = await api.selectFolder(currentPath);
    
    if (result.success && result.path) {
        AppState.setSavePath(result.path);
        logger.logKey('msg_save_path_updated', result.path);
    } else if (result.message && result.message !== '未选择文件夹') {
        logger.log(result.message);
    }
}

/* ===================== 初始化 ===================== */

document.addEventListener('DOMContentLoaded', async () => {
    logger.logKey('msg_app_start');
    
    // 从URL获取访问令牌
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
        AppState.setAccessToken(token);
        logger.logKey('msg_token_loaded');
    }
    
    initializeUI();
    
    // 初始化模块
    const success = await api.init();
    if (success) {
        logger.logKey('msg_ready');
    } else {
        logger.logKey('msg_init_partial');
        logger.logKey('msg_check_network');
    }
});

/* ===================== 热键支持 ===================== */

document.addEventListener('keydown', (e) => {
    // Ctrl+Enter 快速下载
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const downloadBtn = document.getElementById('downloadBtn');
        if (downloadBtn.style.display !== 'none' && !downloadBtn.disabled) {
            handleAddToQueue();
        }
    }
});

/* ===================== 窗口控制 (无边框模式) ===================== */

function initWindowControls() {
    const minBtn = document.getElementById('winMinimize');
    const maxBtn = document.getElementById('winMaximize');
    const closeBtn = document.getElementById('winClose');
    
    if (!minBtn || !maxBtn || !closeBtn) return;
    
    // 检测是否在 pywebview 环境中
    const isPyWebView = () => window.pywebview && window.pywebview.api;
    
    minBtn.addEventListener('click', () => {
        if (isPyWebView()) {
            window.pywebview.api.minimize_window();
        }
    });
    
    maxBtn.addEventListener('click', () => {
        if (isPyWebView()) {
            window.pywebview.api.toggle_maximize();
        }
    });
    
    closeBtn.addEventListener('click', () => {
        if (isPyWebView()) {
            window.pywebview.api.close_window();
        } else {
            window.close();
        }
    });
}

// 初始化窗口控制
document.addEventListener('DOMContentLoaded', initWindowControls);
