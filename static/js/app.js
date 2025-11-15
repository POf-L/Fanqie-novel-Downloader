/* ===================== 全局状态管理 ===================== */

const AppState = {
    isDownloading: false,
    currentProgress: 0,
    savePath: '',
    
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

/* ===================== 日志管理 ===================== */

class Logger {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.maxEntries = 100;
    }
    
    log(message) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.textContent = `[${this.getTime()}] ${message}`;
        this.container.appendChild(entry);
        
        // 自动滚动到底部
        const logContainer = this.container.parentElement;
        logContainer.scrollTop = logContainer.scrollHeight;
        
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
    constructor(baseURL = 'http://127.0.0.1:5000') {
        this.baseURL = baseURL;
        this.statusPoll = null;
    }
    
    async request(endpoint, options = {}) {
        try {
            const url = `${this.baseURL}${endpoint}`;
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            logger.log(`❌ 请求失败: ${error.message}`);
            throw error;
        }
    }
    
    async init() {
        logger.log('🔄 初始化应用...');
        try {
            const result = await this.request('/api/init', { method: 'POST' });
            if (result.success) {
                logger.log('✅ 核心模块加载完成');
            } else {
                logger.log('⚠️ 模块加载失败: ' + result.message);
            }
            return result.success;
        } catch (error) {
            logger.log('❌ 初始化失败');
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
                logger.log(`❌ ${result.message}`);
                return null;
            }
        } catch (error) {
            logger.log(`❌ 获取书籍信息失败: ${error.message}`);
            return null;
        }
    }
    
    async startDownload(bookId, savePath, fileFormat, startChapter, endChapter) {
        try {
            const result = await this.request('/api/download', {
                method: 'POST',
                body: JSON.stringify({
                    book_id: bookId,
                    save_path: savePath,
                    file_format: fileFormat,
                    start_chapter: startChapter,
                    end_chapter: endChapter
                })
            });
            
            if (result.success) {
                logger.log('✅ 下载任务已启动');
                AppState.setDownloading(true);
                this.startStatusPolling();
                return true;
            } else {
                logger.log(`❌ ${result.message}`);
                return false;
            }
        } catch (error) {
            logger.log(`❌ 启动下载失败: ${error.message}`);
            return false;
        }
    }
    
    async cancelDownload() {
        try {
            const result = await this.request('/api/cancel', { method: 'POST' });
            if (result.success) {
                logger.log('⏹ 下载已取消');
                AppState.setDownloading(false);
                this.stopStatusPolling();
                return true;
            }
        } catch (error) {
            logger.log(`❌ 取消下载失败: ${error.message}`);
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
        
        // 更新消息
        if (status.message) {
            logger.log(status.message);
        }
        
        // 更新书籍名称
        if (status.book_name) {
            document.getElementById('bookName').textContent = status.book_name;
        }
        
        // 更新状态文本
        if (status.is_downloading) {
            document.getElementById('statusText').textContent = '下载中...';
        } else if (progress === 100) {
            document.getElementById('statusText').textContent = '✅ 已完成';
        } else {
            document.getElementById('statusText').textContent = '准备就绪';
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
            logger.log(`❌ 文件夹选择失败: ${error.message}`);
            return { success: false };
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
}

const api = new APIClient();

/* ===================== UI 事件处理 ===================== */

function initializeUI() {
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
    
    // 版本信息
    document.getElementById('version').textContent = '1.0.0';
    
    checkForUpdate();
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

function showUpdateModal(updateInfo) {
    const modal = document.getElementById('updateModal');
    const currentVersion = document.getElementById('currentVersion');
    const latestVersion = document.getElementById('latestVersion');
    const updateDescription = document.getElementById('updateDescription');
    const downloadUpdateBtn = document.getElementById('downloadUpdateBtn');
    const closeUpdateBtn = document.getElementById('closeUpdateBtn');
    const updateModalClose = document.getElementById('updateModalClose');
    
    currentVersion.textContent = updateInfo.current_version;
    latestVersion.textContent = updateInfo.latest_version;
    
    const releaseBody = updateInfo.release_info?.body || updateInfo.message || '暂无更新说明';
    updateDescription.innerHTML = releaseBody.replace(/\n/g, '<br>');
    
    modal.style.display = 'flex';
    
    downloadUpdateBtn.onclick = () => {
        window.open(updateInfo.url || updateInfo.release_info?.html_url, '_blank');
        modal.style.display = 'none';
    };
    
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
    
    logger.log(`📚 正在获取书籍信息: ${bookId}`);
    
    const bookInfo = await api.getBookInfo(bookId);
    if (!bookInfo) {
        alert('获取书籍信息失败，请检查ID是否正确');
        return;
    }
    
    showConfirmDialog(bookInfo, savePath, fileFormat);
}

function showConfirmDialog(bookInfo, savePath, fileFormat) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>📖 确认下载</h2>
                <button class="close-btn" onclick="this.closest('.modal').remove()">✕</button>
            </div>
            
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
                <div class="chapter-range">
                    <label>
                        <input type="radio" name="chapterMode" value="all" checked>
                        下载全部章节
                    </label>
                    <label>
                        <input type="radio" name="chapterMode" value="range">
                        自定义章节范围
                    </label>
                </div>
                
                <div class="chapter-inputs" id="chapterInputs" style="display: none;">
                    <div class="input-row">
                        <label>起始章节:</label>
                        <select id="startChapter" class="chapter-select">
                            ${bookInfo.chapters.map((ch, idx) => 
                                `<option value="${idx}">${idx + 1}. ${ch.title}</option>`
                            ).join('')}
                        </select>
                    </div>
                    <div class="input-row">
                        <label>结束章节:</label>
                        <select id="endChapter" class="chapter-select">
                            ${bookInfo.chapters.map((ch, idx) => 
                                `<option value="${idx}" ${idx === bookInfo.chapters.length - 1 ? 'selected' : ''}>${idx + 1}. ${ch.title}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
            </div>
            
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">取消</button>
                <button class="btn btn-primary" id="confirmDownloadBtn">开始下载</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const chapterModeInputs = modal.querySelectorAll('input[name="chapterMode"]');
    const chapterInputs = modal.querySelector('#chapterInputs');
    
    chapterModeInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            chapterInputs.style.display = e.target.value === 'range' ? 'block' : 'none';
        });
    });
    
    modal.querySelector('#confirmDownloadBtn').addEventListener('click', () => {
        const mode = modal.querySelector('input[name="chapterMode"]:checked').value;
        let startChapter = null;
        let endChapter = null;
        
        if (mode === 'range') {
            startChapter = parseInt(modal.querySelector('#startChapter').value);
            endChapter = parseInt(modal.querySelector('#endChapter').value);
            
            if (startChapter > endChapter) {
                alert('起始章节不能大于结束章节');
                return;
            }
            
            logger.log(`📚 准备下载《${bookInfo.book_name}》`);
            logger.log(`📑 章节范围: 第 ${startChapter + 1} 章 - 第 ${endChapter + 1} 章`);
        } else {
            logger.log(`📚 准备下载《${bookInfo.book_name}》全部章节`);
        }
        
        logger.log(`💾 保存路径: ${savePath}`);
        logger.log(`📄 文件格式: ${fileFormat.toUpperCase()}`);
        
        api.startDownload(bookInfo.book_id, savePath, fileFormat, startChapter, endChapter);
        modal.remove();
    });
}

async function handleCancel() {
    if (confirm('确定要取消下载吗？')) {
        await api.cancelDownload();
    }
}

function handleClear() {
    if (confirm('确定要清理所有设置吗？')) {
        document.getElementById('bookId').value = '';
        document.getElementById('savePath').value = '';
        document.querySelector('input[name="format"]').checked = true;
        logger.clear();
        logger.log('🧹 设置已清理');
    }
}

async function handleBrowse() {
    const currentPath = document.getElementById('savePath').value || '';
    
    logger.log('📁 打开文件夹选择对话框...');
    
    const result = await api.selectFolder(currentPath);
    
    if (result.success && result.path) {
        AppState.setSavePath(result.path);
        logger.log(`✅ 保存路径已更新: ${result.path}`);
    } else if (result.message && result.message !== '未选择文件夹') {
        logger.log(`❌ ${result.message}`);
    }
}

/* ===================== 初始化 ===================== */

document.addEventListener('DOMContentLoaded', async () => {
    logger.log('🚀 应用启动...');
    initializeUI();
    
    // 初始化模块
    const success = await api.init();
    if (success) {
        logger.log('准备就绪，请输入书籍信息开始下载');
    } else {
        logger.log('⚠️ 应用初始化完成，但部分功能可能不可用');
        logger.log('如遇到问题，请检查网络连接或重启应用');
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
