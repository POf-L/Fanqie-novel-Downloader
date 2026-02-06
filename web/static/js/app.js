/* ===================== Toast 消息组件 ===================== */

class Toast {
    static container = null;
    static toasts = new Map();
    static idCounter = 0;

    static init() {
        if (this.container) return;
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);
    }

    static show(message, type = 'info', duration = 5000) {
        this.init();
        const id = ++this.idCounter;
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-icon">${this.getIcon(type)}</div>
            <div class="toast-message">${message}</div>
            <button class="toast-close" onclick="Toast.dismiss(${id})">×</button>
        `;
        
        this.container.appendChild(toast);
        this.toasts.set(id, toast);
        
        // 触发动画
        requestAnimationFrame(() => toast.classList.add('toast-show'));
        
        // 自动消失
        if (duration > 0) {
            setTimeout(() => this.dismiss(id), duration);
        }
        
        return id;
    }

    static success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    }

    static error(message, duration = 5000) {
        return this.show(message, 'error', duration);
    }

    static warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }

    static info(message, duration = 5000) {
        return this.show(message, 'info', duration);
    }

    static dismiss(id) {
        const toast = this.toasts.get(id);
        if (!toast) return;
        
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hide');
        
        setTimeout(() => {
            toast.remove();
            this.toasts.delete(id);
        }, 300);
    }

    static getIcon(type) {
        const icons = {
            success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>',
            error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
            warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
            info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
        };
        return icons[type] || icons.info;
    }
}

/* ===================== 队列管理器 ===================== */

class QueueManager {
    constructor() {
        this.storageKey = 'fanqie_download_queue_v2';
        this.statusPollInterval = null;
        this.serverTasks = [];  // 服务器端任务状态
        this.visibilityHandler = null;
    }
    
    // 获取状态图标
    getStatusIcon(status) {
        const icons = {
            pending: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
            downloading: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>',
            completed: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
            failed: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
            skipped: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><polygon points="5 4 15 12 5 20 5 4"></polygon><line x1="19" y1="5" x2="19" y2="19"></line></svg>'
        };
        return icons[status] || icons.pending;
    }
    
    // 获取状态文本
    getStatusText(status) {
        const texts = {
            pending: '等待中',
            downloading: '下载中',
            completed: '已完成',
            failed: '失败',
            skipped: '已跳过'
        };
        return texts[status] || status;
    }
    
    // 从服务器获取队列状态
    async fetchQueueStatus() {
        try {
            const headers = { 'Content-Type': 'application/json' };
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            const response = await fetch('/api/queue/status', { headers });
            const result = await response.json();
            if (result.success) {
                this.serverTasks = result.data.tasks || [];
                return result.data;
            }
        } catch (e) {
            console.error('获取队列状态失败:', e);
        }
        return null;
    }
    
    // 跳过当前任务
    async skipCurrent() {
        try {
            const headers = { 'Content-Type': 'application/json' };
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            const response = await fetch('/api/queue/skip', {
                method: 'POST',
                headers
            });
            const result = await response.json();
            if (result.success) {
                Toast.success(result.message || '已跳过当前任务');
                return true;
            } else {
                Toast.error(result.message || '跳过失败');
            }
        } catch (e) {
            Toast.error('跳过失败: ' + e.message);
        }
        return false;
    }
    
    // 重试任务
    async retryTask(taskId) {
        try {
            const headers = { 'Content-Type': 'application/json' };
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            const response = await fetch('/api/queue/retry', {
                method: 'POST',
                headers,
                body: JSON.stringify({ task_id: taskId })
            });
            const result = await response.json();
            if (result.success) {
                Toast.success(result.message || '任务已重置');
                return true;
            } else {
                Toast.error(result.message || '重试失败');
            }
        } catch (e) {
            Toast.error('重试失败: ' + e.message);
        }
        return false;
    }
    
    // 重试所有失败任务
    async retryAllFailed() {
        try {
            const headers = { 'Content-Type': 'application/json' };
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            const response = await fetch('/api/queue/retry', {
                method: 'POST',
                headers,
                body: JSON.stringify({ retry_all: true })
            });
            const result = await response.json();
            if (result.success) {
                Toast.success(result.message || '已重置所有失败任务');
                return true;
            } else {
                Toast.error(result.message || '重试失败');
            }
        } catch (e) {
            Toast.error('重试失败: ' + e.message);
        }
        return false;
    }
    
    // 强制保存
    async forceSave() {
        try {
            const headers = { 'Content-Type': 'application/json' };
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            const response = await fetch('/api/queue/force-save', {
                method: 'POST',
                headers
            });
            const result = await response.json();
            if (result.success) {
                Toast.success(result.message || '已保存当前进度');
                return true;
            } else {
                Toast.error(result.message || '保存失败');
            }
        } catch (e) {
            Toast.error('保存失败: ' + e.message);
        }
        return false;
    }
    
    // 检查断点续传
    async checkResume(bookId) {
        try {
            const headers = { 'Content-Type': 'application/json' };
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            const response = await fetch('/api/download/resume-check', {
                method: 'POST',
                headers,
                body: JSON.stringify({ book_id: bookId })
            });
            const result = await response.json();
            if (result.success) {
                return result.data;
            }
        } catch (e) {
            console.error('检查断点续传失败:', e);
        }
        return null;
    }
    
    // 开始状态轮询
    startStatusPolling() {
        if (this.statusPollInterval) return;
        this.statusPollInterval = setInterval(async () => {
            if (document.hidden) return;
            const status = await this.fetchQueueStatus();
            if (status) {
                this.updateQueueUI(status);
                // 如果队列完成，停止轮询
                if (!status.is_running) {
                    this.stopStatusPolling();
                    this.showQueueSummary(status);
                }
            }
        }, 1000);
        
        if (!this.visibilityHandler) {
            this.visibilityHandler = async () => {
                if (!document.hidden && this.statusPollInterval) {
                    const status = await this.fetchQueueStatus();
                    if (status) {
                        this.updateQueueUI(status);
                        if (!status.is_running) {
                            this.stopStatusPolling();
                            this.showQueueSummary(status);
                        }
                    }
                }
            };
            document.addEventListener('visibilitychange', this.visibilityHandler);
        }
    }
    
    // 停止状态轮询
    stopStatusPolling() {
        if (this.statusPollInterval) {
            clearInterval(this.statusPollInterval);
            this.statusPollInterval = null;
        }
        if (this.visibilityHandler) {
            document.removeEventListener('visibilitychange', this.visibilityHandler);
            this.visibilityHandler = null;
        }
    }
    
    // 更新队列UI
    updateQueueUI(status) {
        const list = document.getElementById('queueList');
        if (!list) return;

        const tasks = status.tasks || [];
        if (tasks.length === 0) return;

        // 更新每个任务的状态显示
        tasks.forEach(task => {
            const taskEl = list.querySelector(`[data-task-id="${task.id}"]`);
            if (taskEl) {
                const statusEl = taskEl.querySelector('.queue-item-status');
                const nextStatus = task.status || 'pending';
                if (statusEl) {
                    if (taskEl.dataset.status !== nextStatus) {
                        statusEl.innerHTML = `${this.getStatusIcon(nextStatus)} ${this.getStatusText(nextStatus)}`;
                        statusEl.className = `queue-item-status status-${nextStatus}`;
                        taskEl.dataset.status = nextStatus;
                    }
                }

                const progressEl = taskEl.querySelector('.queue-item-progress');
                const nextProgress = typeof task.progress === 'number' ? task.progress : 0;
                if (progressEl && nextStatus === 'downloading') {
                    progressEl.style.display = 'block';
                    const fill = progressEl.querySelector('.progress-fill');
                    if (fill && taskEl.dataset.progress !== String(nextProgress)) {
                        fill.style.width = `${nextProgress}%`;
                        taskEl.dataset.progress = String(nextProgress);
                    }
                } else if (progressEl) {
                    progressEl.style.display = 'none';
                    taskEl.dataset.progress = String(nextProgress);
                }

                // 显示/隐藏重试按钮
                const retryBtn = taskEl.querySelector('.retry-btn');
                if (retryBtn) {
                    const shouldShowRetry = nextStatus === 'failed';
                    if (retryBtn.dataset.visible !== String(shouldShowRetry)) {
                        retryBtn.style.display = shouldShowRetry ? 'inline-flex' : 'none';
                        retryBtn.dataset.visible = String(shouldShowRetry);
                    }
                }

                // 任务完成或失败时，从本地队列中删除
                if (nextStatus === 'completed' || nextStatus === 'failed' || nextStatus === 'skipped') {
                    AppState.removeFromQueue(task.id);
                }
            }
        });

        // 更新摘要
        const summary = document.getElementById('queueSummary');
        if (summary) {
            const completed = status.completed_count || 0;
            const failed = status.failed_count || 0;
            const skipped = status.skipped_count || 0;
            const total = status.total_tasks || 0;
            const summaryText = `${completed}/${total} 完成, ${failed} 失败, ${skipped} 跳过`;
            if (summary.textContent !== summaryText) {
                summary.textContent = summaryText;
            }
        }
    }
    
    // 显示队列完成摘要
    showQueueSummary(status) {
        const completed = status.completed_count || 0;
        const failed = status.failed_count || 0;
        const skipped = status.skipped_count || 0;
        const total = status.total_tasks || 0;
        
        let message = `队列下载完成: ${completed}/${total} 成功`;
        if (failed > 0) message += `, ${failed} 失败`;
        if (skipped > 0) message += `, ${skipped} 跳过`;
        
        if (failed > 0) {
            Toast.warning(message + '。点击"重试全部"可重新下载失败任务。');
        } else {
            Toast.success(message);
        }
    }
}

// 全局队列管理器实例
const queueManager = new QueueManager();

/* ===================== 确认对话框组件 ===================== */

class ConfirmDialog {
    static show(options = {}) {
        return new Promise((resolve) => {
            const {
                title = '确认',
                message = '',
                confirmText = '确定',
                cancelText = '取消',
                type = 'info' // info, warning, danger
            } = options;

            const modal = document.createElement('div');
            modal.className = 'modal confirm-modal';
            modal.innerHTML = `
                <div class="modal-content confirm-dialog confirm-${type}">
                    <div class="modal-header">
                        <h3>${title}</h3>
                        <button class="modal-close" type="button">×</button>
                    </div>
                    <div class="modal-body">
                        <p class="confirm-message">${message}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary cancel-btn" type="button">${cancelText}</button>
                        <button class="btn btn-primary confirm-btn ${type === 'danger' ? 'btn-danger' : ''}" type="button">${confirmText}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
            modal.style.display = 'flex';

            const close = (result) => {
                modal.remove();
                resolve(result);
            };

            modal.querySelector('.modal-close').addEventListener('click', () => close(false));
            modal.querySelector('.cancel-btn').addEventListener('click', () => close(false));
            modal.querySelector('.confirm-btn').addEventListener('click', () => close(true));
            modal.addEventListener('click', (e) => {
                if (e.target === modal) close(false);
            });
        });
    }
}

/* ===================== 重复下载确认对话框 ===================== */

function showDuplicateDownloadDialog(bookInfo, record, downloadTime) {
    return new Promise((resolve) => {
        const fileExists = record.file_exists;
        const modal = document.createElement('div');
        modal.className = 'modal confirm-modal';
        modal.innerHTML = `
            <div class="modal-content confirm-dialog confirm-warning" style="max-width: 450px;">
                <div class="modal-header">
                    <h3>重复下载提示</h3>
                    <button class="modal-close" type="button">×</button>
                </div>
                <div class="modal-body">
                    <div style="margin-bottom: 15px;">
                        <p style="color: #ffaa00; margin-bottom: 10px;">
                            ⚠️ 该书籍已下载过
                        </p>
                        <div style="background: #1a1a2e; padding: 12px; border-radius: 4px; font-size: 12px;">
                            <p style="margin: 4px 0;"><strong>书名:</strong> ${record.book_name}</p>
                            <p style="margin: 4px 0;"><strong>下载时间:</strong> ${downloadTime}</p>
                            <p style="margin: 4px 0;"><strong>文件状态:</strong> 
                                ${fileExists 
                                    ? '<span style="color: #00ff00;">文件存在</span>' 
                                    : '<span style="color: #ff4444;">文件已移动或删除</span>'}
                            </p>
                        </div>
                    </div>
                </div>
                <div class="modal-footer" style="display: flex; gap: 8px; justify-content: flex-end;">
                    <button class="btn btn-secondary cancel-btn" type="button">取消</button>
                    ${fileExists ? `<button class="btn btn-secondary open-btn" type="button">打开已有文件</button>` : ''}
                    <button class="btn btn-primary download-btn" type="button">仍然下载</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.style.display = 'flex';

        const close = (action) => {
            modal.remove();
            resolve(action);
        };

        modal.querySelector('.modal-close').addEventListener('click', () => close('cancel'));
        modal.querySelector('.cancel-btn').addEventListener('click', () => close('cancel'));
        modal.querySelector('.download-btn').addEventListener('click', () => close('download'));
        
        const openBtn = modal.querySelector('.open-btn');
        if (openBtn) {
            openBtn.addEventListener('click', () => close('open'));
        }
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) close('cancel');
        });
    });
}

/* ===================== 文件夹浏览器组件 ===================== */

class FolderBrowser {
    static async show(options = {}) {
        return new Promise((resolve) => {
            const {
                title = '选择文件夹',
                initialPath = ''
            } = options;

            const modal = document.createElement('div');
            modal.className = 'modal folder-browser-modal';
            modal.innerHTML = `
                <div class="modal-content folder-browser-dialog">
                    <div class="modal-header">
                        <h3><iconify-icon icon="line-md:folder-open-twotone"></iconify-icon> ${title}</h3>
                        <button class="modal-close" type="button"><iconify-icon icon="line-md:close"></iconify-icon></button>
                    </div>
                    <div class="modal-body">
                        <div class="folder-browser-path">
                            <input type="text" class="form-input path-input" readonly>
                        </div>
                        <div class="folder-browser-toolbar">
                            <div class="folder-browser-nav">
                                <button class="btn btn-sm btn-secondary nav-up" type="button" disabled>
                                    <iconify-icon icon="line-md:chevron-left"></iconify-icon>
                                </button>
                            </div>
                            <div class="folder-browser-quick" style="display: none;"></div>
                            <div class="folder-browser-drives" style="display: none;"></div>
                        </div>
                        <div class="folder-browser-list">
                            <div class="folder-loading"><iconify-icon icon="line-md:loading-twotone-loop"></iconify-icon></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary cancel-btn" type="button"><iconify-icon icon="line-md:close"></iconify-icon></button>
                        <button class="btn btn-primary select-btn" type="button"><iconify-icon icon="line-md:confirm"></iconify-icon></button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
            modal.style.display = 'flex';

            const pathInput = modal.querySelector('.path-input');
            const navUp = modal.querySelector('.nav-up');
            const quickContainer = modal.querySelector('.folder-browser-quick');
            const drivesContainer = modal.querySelector('.folder-browser-drives');
            const listContainer = modal.querySelector('.folder-browser-list');
            const selectBtn = modal.querySelector('.select-btn');

            let currentPath = initialPath;
            let parentPath = null;
            let selectedPath = null; // 当前选中的文件夹路径

            const close = (result) => {
                modal.remove();
                resolve(result);
            };

            const updatePathDisplay = () => {
                // 更新路径显示：如果有选中的文件夹，显示选中的路径，否则显示当前路径
                const displayPath = selectedPath || currentPath;
                pathInput.value = displayPath;

                // 更新确认按钮的状态和文本
                const selectedFolder = selectedPath ? selectedPath.split(/[/\\]/).pop() : null;
                if (selectedFolder) {
                    selectBtn.innerHTML = `<iconify-icon icon="line-md:confirm"></iconify-icon> 选择 "${selectedFolder}"`;
                } else {
                    selectBtn.innerHTML = `<iconify-icon icon="line-md:confirm"></iconify-icon> 选择当前文件夹`;
                }
            };

            const loadDirectory = async (path) => {
                listContainer.innerHTML = `<div class="folder-loading"><iconify-icon icon="line-md:loading-twotone-loop"></iconify-icon></div>`;
                
                try {
                    const headers = { 'Content-Type': 'application/json' };
                    if (AppState.accessToken) {
                        headers['X-Access-Token'] = AppState.accessToken;
                    }
                    const response = await fetch('/api/list-directory', {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify({ path: path || '' })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        currentPath = result.data.current_path;
                        parentPath = result.data.parent_path;
                        selectedPath = null; // 重置选中状态
                        navUp.disabled = result.data.is_root;

                        // 更新路径显示
                        updatePathDisplay();
                        
                        // 显示快捷路径
                        if (result.data.quick_paths && result.data.quick_paths.length > 0) {
                            quickContainer.style.display = 'flex';
                            quickContainer.innerHTML = result.data.quick_paths.map(q => 
                                `<button class="btn btn-sm btn-secondary quick-btn" data-path="${q.path}" title="${q.name}">
                                    <iconify-icon icon="${q.icon}"></iconify-icon>
                                </button>`
                            ).join('');
                            
                            quickContainer.querySelectorAll('.quick-btn').forEach(btn => {
                                btn.addEventListener('click', () => loadDirectory(btn.dataset.path));
                            });
                        }
                        
                        // 显示驱动器列表 (Windows)
                        if (result.data.drives && result.data.drives.length > 0) {
                            drivesContainer.style.display = 'flex';
                            drivesContainer.innerHTML = result.data.drives.map(d => 
                                `<button class="btn btn-sm btn-secondary drive-btn" data-path="${d.path}">${d.name}</button>`
                            ).join('');
                            
                            drivesContainer.querySelectorAll('.drive-btn').forEach(btn => {
                                btn.addEventListener('click', () => loadDirectory(btn.dataset.path));
                            });
                        } else {
                            drivesContainer.style.display = 'none';
                        }
                        
                        // 显示目录列表
                        if (result.data.directories.length === 0) {
                            listContainer.innerHTML = `<div class="folder-empty"><iconify-icon icon="line-md:folder-off-twotone"></iconify-icon></div>`;
                        } else {
                            listContainer.innerHTML = result.data.directories.map(d => `
                                <div class="folder-item" data-path="${d.path}">
                                    <iconify-icon icon="line-md:folder-twotone"></iconify-icon>
                                    <span>${d.name}</span>
                                </div>
                            `).join('');
                            
                            listContainer.querySelectorAll('.folder-item').forEach(item => {
                                item.addEventListener('dblclick', () => loadDirectory(item.dataset.path));
                                item.addEventListener('click', (e) => {
                                    e.stopPropagation(); // 阻止事件冒泡
                                    // 移除所有选中状态
                                    listContainer.querySelectorAll('.folder-item').forEach(i => i.classList.remove('selected'));
                                    // 选中当前项
                                    item.classList.add('selected');
                                    // 设置选中的路径
                                    selectedPath = item.dataset.path;
                                    // 更新路径显示
                                    updatePathDisplay();
                                });
                            });

                            // 点击空白区域取消选中
                            listContainer.addEventListener('click', (e) => {
                                if (e.target === listContainer) {
                                    // 清除所有选中状态
                                    listContainer.querySelectorAll('.folder-item').forEach(i => i.classList.remove('selected'));
                                    selectedPath = null;
                                    updatePathDisplay();
                                }
                            });
                        }
                    } else {
                        listContainer.innerHTML = `<div class="folder-error"><iconify-icon icon="line-md:alert"></iconify-icon> ${result.message || 'Error'}</div>`;
                    }
                } catch (e) {
                    console.error('Folder browser error:', e);
                    listContainer.innerHTML = `<div class="folder-error"><iconify-icon icon="line-md:alert"></iconify-icon></div>`;
                }
            };

            // 事件绑定
            modal.querySelector('.modal-close').addEventListener('click', () => close(null));
            modal.querySelector('.cancel-btn').addEventListener('click', () => close(null));
            modal.addEventListener('click', (e) => {
                if (e.target === modal) close(null);
            });

            navUp.addEventListener('click', () => {
                if (parentPath) loadDirectory(parentPath);
            });

            selectBtn.addEventListener('click', async () => {
                // 使用选中的路径，如果没有选中则使用当前路径
                const pathToSelect = selectedPath || currentPath;

                if (pathToSelect) {
                    try {
                        const headers = { 'Content-Type': 'application/json' };
                        if (AppState.accessToken) {
                            headers['X-Access-Token'] = AppState.accessToken;
                        }
                        await fetch('/api/select-folder', {
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify({ path: pathToSelect })
                        });
                    } catch (e) {
                        console.error('Save path failed:', e);
                    }
                    close(pathToSelect);
                }
            });

            // 初始加载
            loadDirectory(initialPath);
        });
    }
}

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
        const input = document.getElementById('savePath');
        if (input) {
            input.value = path;
            // 延迟执行确保 DOM 已完全渲染
            setTimeout(() => {
                requestAnimationFrame(() => {
                    adjustPathFontSize(input);
                });
            }, 50);
        }
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
        
        if (this.isDownloading) {
            downloadBtn.style.display = 'none';
            cancelBtn.style.display = 'inline-block';
            bookIdInput.disabled = true;
            browseBtn.disabled = true;
            if (startQueueBtn) startQueueBtn.disabled = true;
            if (clearQueueBtn) clearQueueBtn.disabled = true;
        } else {
            downloadBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'none';
            bookIdInput.disabled = false;
            browseBtn.disabled = false;
            if (startQueueBtn) startQueueBtn.disabled = false;
            if (clearQueueBtn) clearQueueBtn.disabled = false;
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
        this.messages = {
            // 应用相关
            'msg_app_start': '应用启动',
            'msg_version_info': '版本信息: ',
            'msg_fetch_version_fail': '获取版本信息失败',
            'msg_init_app': '初始化应用',
            'msg_module_loaded': '模块加载成功',
            'msg_module_fail': '模块加载失败: ',
            'msg_init_fail': '初始化失败',
            'msg_token_loaded': '访问令牌已加载',
            'msg_ready': '应用就绪',
            'msg_init_partial': '部分初始化成功',
            'msg_check_network': '请检查网络连接',
            
            // 搜索相关
            'msg_searching': '正在搜索: ',
            'msg_search_fail': '搜索失败: ',
            'log_search_success': '搜索成功，找到 ',
            'log_search_no_results_x': '没有找到搜索结果',
            'log_selected': '已选择: ',
            
            // 书籍信息相关
            'msg_book_info_fail': '获取书籍信息失败: ',
            'log_get_chapter_list': '获取章节列表: ',
            'log_confirmed_selection': '已确认选择，共 ',
            'log_cancel_selection': '已取消选择',
            
            // 下载相关
            'msg_task_started': '下载任务已开始',
            'msg_start_download_fail': '开始下载失败: ',
            'msg_download_cancelled': '下载已取消',
            'msg_cancel_fail': '取消下载失败: ',
            'msg_added_to_queue': '已添加到下载队列: ',
            'msg_removed_from_queue': '已从队列中移除: ',
            'msg_queue_started': '队列开始下载，共 ',
            'msg_queue_cleared': '队列已清空',
            'log_prepare_download': '准备下载: ',
            'log_chapter_range': '章节范围: ',
            'log_mode_manual': '手动模式，共 ',
            'log_download_all': '下载全部章节: ',
            'log_show_dialog_fail': '显示对话框失败: ',
            
            // 文件夹相关
            'msg_folder_fail': '文件夹操作失败: ',
            'msg_open_folder_dialog': '打开文件夹对话框',
            'msg_save_path_updated': '保存路径已更新: ',
            'msg_settings_cleared': '设置已清除',
            
            // 其他
            'log_scp_access': '已切换到单章模式',
            'log_scp_revert': '已退出单章模式'
        };
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
                setTimeout(type, speed);
            } else {
                entry.classList.remove('typing-cursor');
                // 打字完成后滚动到底部
                const logSection = document.getElementById('logContainer');
                if (logSection) {
                    logSection.scrollTop = logSection.scrollHeight;
                }
            }
        };
        
        type();
        
        // 立即滚动一次，确保新条目可见
        const logSection = document.getElementById('logContainer');
        if (logSection) {
            logSection.scrollTop = logSection.scrollHeight;
        }
        
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
            let text = this.messages[data.key] || data.key;
            // 如果有参数，将它们附加到文本后面
            if (data.args && data.args.length > 0) {
                // 对于某些特殊的键，需要特殊处理参数格式
                if (data.key === 'log_selected') {
                    // 格式: 已选择: 书籍名 (ID)
                    text += data.args[0] + ' (' + data.args[1] + ')';
                } else if (data.key === 'log_search_success') {
                    // 格式: 搜索成功，找到 X 本书
                    text += data.args[0] + ' 本书';
                } else if (data.key === 'log_confirmed_selection') {
                    // 格式: 已确认选择，共 X 章
                    text += data.args[0] + ' 章';
                } else if (data.key === 'log_mode_manual') {
                    // 格式: 手动模式，共 X 章
                    text += data.args[0] + ' 章';
                } else if (data.key === 'log_chapter_range') {
                    // 格式: 章节范围: X - Y
                    text += data.args[0] + ' - ' + data.args[1];
                } else if (data.key === 'msg_queue_started') {
                    // 格式: 队列开始下载，共 X 个任务
                    text += data.args[0] + ' 个任务';
                } else {
                    // 默认处理：直接连接参数
                    text += data.args.join('');
                }
            }
            return text;
        } else {
            return data.message;
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
        this.visibilityHandler = null;
        this.lastStatusSnapshot = {
            progress: null,
            statusKey: '',
            queueInfo: '',
            bookName: ''
        };
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
            
            // 使用自定义解析器处理大整数，避免 JavaScript Number 精度丢失
            // book_id 等字段可能超过 Number.MAX_SAFE_INTEGER (9007199254740991)
            const text = await response.text();
            // 将超过安全整数范围的数字转换为字符串（匹配 16 位及以上的纯数字）
            const safeText = text.replace(/:(\s*)(\d{16,})(\s*[,}\]])/g, ':"$2"$3');
            return JSON.parse(safeText);
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
        const poll = async () => {
            if (document.hidden) return;
            const status = await this.getStatus();
            if (status) {
                this.updateUI(status);
                
                // 如果下载完成或被取消，停止轮询
                if (!status.is_downloading) {
                    this.stopStatusPolling();
                    AppState.setDownloading(false);
                }
            }
        };
        
        this.statusPoll = setInterval(poll, 800);
        
        if (!this.visibilityHandler) {
            this.visibilityHandler = () => {
                if (!document.hidden && this.statusPoll) {
                    poll();
                }
            };
            document.addEventListener('visibilitychange', this.visibilityHandler);
        }
    }
    
    stopStatusPolling() {
        if (this.statusPoll) {
            clearInterval(this.statusPoll);
            this.statusPoll = null;
        }
        if (this.visibilityHandler) {
            document.removeEventListener('visibilitychange', this.visibilityHandler);
            this.visibilityHandler = null;
        }
    }
    
    updateUI(status) {
        // 更新进度
        const progress = typeof status.progress === 'number' ? status.progress : 0;
        if (this.lastStatusSnapshot.progress !== progress) {
            const progressFill = document.getElementById('progressFill');
            const progressPercent = document.getElementById('progressPercent');
            
            progressFill.style.width = progress + '%';
            progressPercent.textContent = progress + '%';
            
            // 更新进度标签徽章
            updateProgressBadge(progress);
            this.lastStatusSnapshot.progress = progress;
        }
        
        // 更新消息队列（显示所有消息，不遗漏）
        if (status.messages && status.messages.length > 0) {
            for (const msg of status.messages) {
                logger.log(msg);
            }
        }
        
        // 更新书籍名称
        if (status.book_name) {
            if (this.lastStatusSnapshot.bookName !== status.book_name) {
                document.getElementById('bookName').textContent = status.book_name;
                this.lastStatusSnapshot.bookName = status.book_name;
            }
        }
        
        // 更新状态文本
        const statusTextEl = document.getElementById('statusText');
        const queueInfo = status.queue_total ? ` (${status.queue_current || 1}/${status.queue_total})` : '';
        const statusKey = status.is_downloading ? 'downloading' : (progress === 100 ? 'completed' : 'ready');
        
        if (this.lastStatusSnapshot.statusKey !== statusKey || this.lastStatusSnapshot.queueInfo !== queueInfo) {
            if (statusKey === 'downloading') {
                statusTextEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg> 下载中${queueInfo}`;
            } else if (statusKey === 'completed') {
                statusTextEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> 下载完成`;
                updateProgressBadge(100);
            } else {
                statusTextEl.textContent = '准备下载';
            }
            this.lastStatusSnapshot.statusKey = statusKey;
            this.lastStatusSnapshot.queueInfo = queueInfo;
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

/* ===================== 路径字体自适应 ===================== */

function adjustPathFontSize(input, retryCount = 0) {
    if (!input || !input.value) return;

    const maxFontSize = 12;
    const minFontSize = 9;
    const maxRetries = 5; // 增加重试次数

    // 获取输入框可用宽度（减去 padding）
    const inputStyle = window.getComputedStyle(input);
    const paddingLeft = parseFloat(inputStyle.paddingLeft) || 0;
    const paddingRight = parseFloat(inputStyle.paddingRight) || 0;
    const availableWidth = input.clientWidth - paddingLeft - paddingRight;

    // 如果可用宽度太小（DOM 未完全渲染），智能重试
    if (availableWidth < 100) {
        if (retryCount < maxRetries) {
            // 延迟重试，等待DOM完全渲染
            setTimeout(() => {
                requestAnimationFrame(() => {
                    adjustPathFontSize(input, retryCount + 1);
                });
            }, 150 * (retryCount + 1)); // 增加延迟：150ms, 300ms, 450ms...
            return;
        } else {
            // 重试次数用尽，使用默认字体
            input.style.fontSize = maxFontSize + 'px';
            input.style.letterSpacing = '0px';
            return;
        }
    }

    // 创建临时测量元素
    const measureSpan = document.createElement('span');
    measureSpan.style.cssText = `
        position: absolute;
        visibility: hidden;
        white-space: nowrap;
        font-family: monospace;
    `;
    document.body.appendChild(measureSpan);

    // 先尝试最大字体，看是否需要调整
    let bestFontSize = maxFontSize;
    let bestLetterSpacing = 0;

    measureSpan.style.fontSize = maxFontSize + 'px';
    measureSpan.style.letterSpacing = '0px';
    measureSpan.textContent = input.value;

    if (measureSpan.offsetWidth <= availableWidth) {
        // 文字宽度小于容器，尝试增加字符间距来占满空间
        const textLength = input.value.length;
        if (textLength > 1) {
            const extraSpace = availableWidth - measureSpan.offsetWidth;
            const letterSpacing = Math.min(extraSpace / (textLength - 1), 2); // 最大间距2px

            measureSpan.style.letterSpacing = letterSpacing + 'px';

            // 验证调整后是否仍然适合
            if (measureSpan.offsetWidth <= availableWidth) {
                bestLetterSpacing = letterSpacing;
            }
        }
    } else {
        // 文字太长，需要缩小字体
        for (let size = maxFontSize - 1; size >= minFontSize; size--) {
            measureSpan.style.fontSize = size + 'px';
            measureSpan.style.letterSpacing = '0px';
            measureSpan.textContent = input.value;

            if (measureSpan.offsetWidth <= availableWidth) {
                bestFontSize = size;

                // 尝试在这个字体大小下增加字符间距
                const textLength = input.value.length;
                if (textLength > 1) {
                    const extraSpace = availableWidth - measureSpan.offsetWidth;
                    const letterSpacing = Math.min(extraSpace / (textLength - 1), 1.5); // 小字体时减少最大间距

                    if (letterSpacing > 0) {
                        measureSpan.style.letterSpacing = letterSpacing + 'px';

                        if (measureSpan.offsetWidth <= availableWidth) {
                            bestLetterSpacing = letterSpacing;
                        }
                    }
                }
                break;
            }
        }

        // 如果最小字体还是放不下，就用最小字体，不加间距
        if (bestFontSize === maxFontSize) {
            bestFontSize = minFontSize;
            bestLetterSpacing = 0;
        }
    }

    // 应用最佳设置
    input.style.fontSize = bestFontSize + 'px';
    input.style.letterSpacing = bestLetterSpacing + 'px';

    document.body.removeChild(measureSpan);
}

// 窗口大小变化时重新调整
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        const pathInput = document.getElementById('savePath');
        if (pathInput && pathInput.value) {
            adjustPathFontSize(pathInput);
        }
    }, 100);
});

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
        return `已选择 ${task.selected_chapters.length} 章`;
    }
    if (typeof task?.start_chapter === 'number' && typeof task?.end_chapter === 'number') {
        return `第 ${task.start_chapter} - ${task.end_chapter} 章`;
    }
    return '全部章节';
}

function renderQueue() {
    const list = document.getElementById('queueList');
    const summary = document.getElementById('queueSummary');
    if (!list || !summary) return;

    const tasks = Array.isArray(AppState.downloadQueue) ? AppState.downloadQueue : [];
    summary.textContent = `队列: ${tasks.length} 个任务`;

    if (tasks.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M3 12h18"></path><path d="M3 18h18"></path></svg>
                </div>
                <div class="empty-state-text">队列为空，请添加下载任务</div>
            </div>
        `;
        return;
    }

    const fragment = document.createDocumentFragment();
    tasks.forEach(task => {
        if (!task) return;

        const item = document.createElement('div');
        item.className = 'queue-item';
        item.dataset.taskId = task.id;

        const title = task.book_name || task.book_id || '未知书籍';
        const meta = [
            task.author || '',
            task.book_id ? `ID: ${task.book_id}` : ''
        ].filter(Boolean).join(' · ');
        
        const status = task.status || 'pending';
        const progressValue = typeof task.progress === 'number' ? task.progress : 0;
        item.dataset.status = status;
        item.dataset.progress = String(progressValue);

        item.innerHTML = `
            <div class="queue-item-main">
                <div class="queue-item-title">${title}</div>
                <div class="queue-item-meta">${meta}</div>
                <div class="queue-item-meta">${formatQueueChapterInfo(task)}</div>
                <div class="queue-item-status status-${status}">
                    ${queueManager.getStatusIcon(status)} ${queueManager.getStatusText(status)}
                </div>
                <div class="queue-item-progress" style="display: ${status === 'downloading' ? 'block' : 'none'};">
                    <div class="progress-bar-mini">
                        <div class="progress-fill" style="width: ${progressValue}%"></div>
                    </div>
                </div>
            </div>
            <div class="queue-item-actions">
                <button class="btn btn-sm btn-text retry-btn" type="button" data-action="retry" style="display: ${status === 'failed' ? 'inline-flex' : 'none'};">重试</button>
                <button class="btn btn-sm btn-text remove-btn" type="button" data-action="remove">移出队列</button>
            </div>
        `;

        fragment.appendChild(item);
    });
    list.replaceChildren(fragment);
}

function initQueueListInteractions() {
    const list = document.getElementById('queueList');
    if (!list || list.dataset.bound === '1') return;
    list.dataset.bound = '1';
    
    list.addEventListener('click', async (e) => {
        const actionBtn = e.target.closest('[data-action]');
        if (!actionBtn) return;
        
        const item = actionBtn.closest('.queue-item');
        if (!item) return;
        
        const taskId = item.dataset.taskId;
        if (!taskId) return;
        
        const task = AppState.downloadQueue.find(t => t && String(t.id) === String(taskId));
        const title = task?.book_name || task?.book_id || '未知书籍';
        
        if (actionBtn.dataset.action === 'remove') {
            AppState.removeFromQueue(taskId);
            logger.logKey('msg_removed_from_queue', title);
            return;
        }
        
        if (actionBtn.dataset.action === 'retry') {
            await queueManager.retryTask(taskId);
            renderQueue();
        }
    });
}

async function handleStartQueueDownload() {
    if (AppState.isDownloading) {
        Toast.warning('下载进行中，请等待完成');
        return;
    }

    const tasks = Array.isArray(AppState.downloadQueue) ? AppState.downloadQueue : [];
    if (tasks.length === 0) {
        Toast.warning('队列为空');
        return;
    }

    const savePath = document.getElementById('savePath').value.trim();
    if (!savePath) {
        Toast.warning('请选择保存路径');
        switchTab('download');
        return;
    }

    const fileFormat = document.querySelector('input[name="format"]:checked').value;

    // 检查重复下载
    const bookIds = tasks.map(t => t.book_id);
    let duplicateBooks = [];
    try {
        const headers = { 'Content-Type': 'application/json' };
        if (AppState.accessToken) {
            headers['X-Access-Token'] = AppState.accessToken;
        }
        const historyResponse = await fetch('/api/download-history/check', {
            method: 'POST',
            headers,
            body: JSON.stringify({ book_ids: bookIds })
        });
        const historyResult = await historyResponse.json();

        if (historyResult.success && historyResult.results) {
            for (const [bookId, record] of Object.entries(historyResult.results)) {
                if (record) {
                    const task = tasks.find(t => t.book_id === bookId);
                    duplicateBooks.push({
                        book_id: bookId,
                        book_name: task?.book_name || record.book_name || bookId,
                        download_time: record.download_time,
                        file_exists: record.file_exists
                    });
                }
            }
        }
    } catch (e) {
        console.warn('Batch download history check failed:', e);
    }

    // 如果有重复下载的书籍，显示确认对话框
    if (duplicateBooks.length > 0) {
        const duplicateList = duplicateBooks.map(b => {
            const time = new Date(b.download_time).toLocaleString();
            const status = b.file_exists
                ? `<span style="color: #00ff00;">文件存在</span>`
                : `<span style="color: #ff4444;">文件已移动或删除</span>`;
            return `<li style="margin: 4px 0;"><strong>${b.book_name}</strong> - ${time} (${status})</li>`;
        }).join('');

        const confirmed = await ConfirmDialog.show({
            title: '重复下载提示',
            message: `
                <div style="margin-bottom: 10px;">
                    <p style="color: #ffaa00;">⚠️ 发现 ${duplicateBooks.length} 本书籍已下载过：</p>
                    <ul style="max-height: 200px; overflow-y: auto; padding-left: 20px; margin: 10px 0; background: #1a1a2e; padding: 12px 12px 12px 30px; border-radius: 4px; font-size: 12px;">
                        ${duplicateList}
                    </ul>
                    <p>是否继续下载？</p>
                </div>
            `,
            type: 'warning'
        });

        if (!confirmed) {
            return;
        }
    }

    const payload = tasks.map(t => ({
        book_id: t.book_id,
        start_chapter: t.start_chapter,
        end_chapter: t.end_chapter,
        selected_chapters: t.selected_chapters
    }));

    const result = await api.startQueue(payload, savePath, fileFormat);
    if (result && result.success) {
        logger.logKey('msg_queue_started', payload.length);
        // 不立即清空队列，等待任务完成后再逐个删除
        AppState.setDownloading(true);
        api.startStatusPolling();
        return;
    }

    const message = result?.message || '启动下载失败';
    logger.log(message);
    Toast.error(message);
}

async function handleClearQueue() {
    const tasks = Array.isArray(AppState.downloadQueue) ? AppState.downloadQueue : [];
    if (tasks.length === 0) return;

    const confirmed = await ConfirmDialog.show({
        title: '确认',
        message: '确定要清空队列吗？',
        type: 'warning'
    });
    if (!confirmed) return;

    AppState.clearQueue();
    logger.logKey('msg_queue_cleared');
}

async function handleLoadFromFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // 重置 input 以便可以再次选择同一文件
    event.target.value = '';
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const headers = {};
        if (AppState.accessToken) {
            headers['X-Access-Token'] = AppState.accessToken;
        }
        
        const response = await fetch('/api/upload-book-list', {
            method: 'POST',
            headers,
            body: formData
        });
        
        const result = await response.json();
        
        if (!result.success) {
            Toast.error('加载文件失败');
            return;
        }
        
        const { books, skipped, valid_count, skipped_count } = result.data;
        
        if (valid_count === 0) {
            Toast.warning('文件中没有有效的书籍ID');
            return;
        }
        
        // 添加到队列
        let addedCount = 0;
        for (const book of books) {
            const task = {
                id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
                book_id: book.book_id,
                book_name: '未知书籍',
                author: '',
                cover_url: '',
                abstract: '',
                chapter_count: 0,
                start_chapter: null,
                end_chapter: null,
                selected_chapters: null,
                added_at: new Date().toISOString(),
                from_file: true,
                source_line: book.source_line
            };
            AppState.addToQueue(task);
            addedCount++;
        }
        
        let message = `已从文件加载 ${addedCount} 本书籍`;
        if (skipped_count > 0) {
            message += ` (跳过 ${skipped_count} 行)`;
        }
        
        Toast.success(message);
        logger.log(message);
        
        // 切换到队列标签
        switchTab('queue');
        
    } catch (e) {
        console.error('Load from file error:', e);
        Toast.error('加载文件失败');
    }
}

/* ===================== UI 事件处理 ===================== */

function initializeUI(skipApiSources = false) {
    // 初始化标签页系统
    initTabSystem();

    // 初始化队列
    AppState.loadQueue();
    renderQueue();
    initQueueListInteractions();
    
    // 初始化保存路径
    api.getSavePath().then(path => {
        if (path) {
            AppState.setSavePath(path);
            // 多重保障：确保路径缩放在各种情况下都能执行
            const ensurePathAdjustment = () => {
                const pathInput = document.getElementById('savePath');
                if (pathInput && pathInput.value) {
                    adjustPathFontSize(pathInput);
                }
            };

            // 立即尝试
            setTimeout(ensurePathAdjustment, 100);

            // DOM完全加载后再次尝试
            if (document.readyState === 'complete') {
                setTimeout(ensurePathAdjustment, 300);
            } else {
                window.addEventListener('load', () => {
                    setTimeout(ensurePathAdjustment, 300);
                }, { once: true });
            }

            // 最终保障：页面完全稳定后再次尝试
            setTimeout(ensurePathAdjustment, 1000);
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
    
    // 从文件加载按钮
    const loadFromFileBtn = document.getElementById('loadFromFileBtn');
    const bookListFileInput = document.getElementById('bookListFileInput');
    if (loadFromFileBtn && bookListFileInput) {
        loadFromFileBtn.addEventListener('click', () => bookListFileInput.click());
        bookListFileInput.addEventListener('change', handleLoadFromFile);
    }
    
    // 版本信息 - 从API获取
    fetchVersion();
    
    // 初始化章节选择弹窗事件
    initChapterModalEvents();
    initSearchListInteractions();
    
    // 语言切换功能已移除

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
    
    // checkForUpdate 已在 DOMContentLoaded 中并发执行
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
const searchBookCache = new Map();

function initSearchListInteractions() {
    const listContainer = document.getElementById('searchResultList');
    if (!listContainer || listContainer.dataset.bound === '1') return;
    listContainer.dataset.bound = '1';
    
    listContainer.addEventListener('click', (e) => {
        const actionBtn = e.target.closest('[data-action]');
        const item = e.target.closest('.search-item');
        
        if (!item) return;
        
        const bookId = item.dataset.bookId;
        const bookData = searchBookCache.get(bookId);
        
        if (actionBtn?.dataset.action === 'toggle-desc') {
            e.stopPropagation();
            const desc = item.querySelector('.search-desc');
            const isCollapsed = desc.classList.contains('collapsed');
            desc.classList.toggle('collapsed', !isCollapsed);
            desc.classList.toggle('expanded', isCollapsed);
            actionBtn.innerHTML = isCollapsed
                ? '<iconify-icon icon="line-md:chevron-small-up"></iconify-icon>'
                : '<iconify-icon icon="line-md:chevron-small-down"></iconify-icon>';
            return;
        }
        
        if (actionBtn?.dataset.action === 'add-queue') {
            e.stopPropagation();
            if (bookData) {
                handleAddToQueue(bookId, {
                    book_name: bookData.book_name,
                    author: bookData.author,
                    abstract: bookData.abstract,
                    cover_url: bookData.cover_url,
                    chapter_count: bookData.chapter_count
                });
            } else {
                handleAddToQueue(bookId);
            }
            return;
        }
        
        if (bookId) {
            selectBook(bookId, bookData?.book_name || item.dataset.bookName || bookId);
        }
    });
}

async function handleSearch() {
    const keyword = document.getElementById('searchKeyword').value.trim();
    if (!keyword) {
        Toast.warning('请输入搜索关键词');
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
    searchBtn.textContent = '搜索';
    
    if (result && result.books) {
        displaySearchResults(result.books, false, result.has_more);
        searchOffset = result.books.length;
        logger.logKey('log_search_success', result.books.length);
    } else {
        displaySearchResults([], false, false);
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
    loadMoreBtn.textContent = '加载更多';
    
    if (result && result.books && result.books.length > 0) {
        displaySearchResults(result.books, true, result.has_more);
        searchOffset += result.books.length;
    } else {
        document.getElementById('loadMoreContainer').style.display = 'none';
    }
}

function displaySearchResults(books, append = false, hasMore = false) {
    const headerContainer = document.getElementById('searchHeader');
    const listContainer = document.getElementById('searchResultList');
    const countSpan = document.getElementById('searchResultCount');
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    
    headerContainer.style.display = 'flex';
    
    if (!append) {
        // 保留加载更多按钮，清除其他内容
        listContainer.innerHTML = '';
        listContainer.appendChild(loadMoreContainer);
        searchBookCache.clear();
    }
    
    if (books.length === 0 && !append) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                </div>
                <div class="empty-state-text">没有找到相关书籍</div>
            </div>
        `;
        countSpan.textContent = '找到 0 本'
        headerContainer.style.display = 'none';
        return;
    }
    
    const fragment = document.createDocumentFragment();
    books.forEach(book => {
        const item = document.createElement('div');
        item.className = 'search-item';
        item.dataset.bookId = book.book_id;
        item.dataset.bookName = book.book_name || '';
        searchBookCache.set(book.book_id, book);
        
        const wordCount = book.word_count ? (book.word_count / 10000).toFixed(1) + ' 万字' : '';
        const chapterCount = book.chapter_count ? book.chapter_count + ' 章' : '';
        const status = book.status || '';
        
        // Translate status
        let displayStatus = status;
        let statusClass = 'ongoing';
        
        if (status === '完结' || status === '已完结') {
            displayStatus = '已完结';
            statusClass = 'complete';
        } else if (status === '连载' || status === '连载中') {
            displayStatus = '连载中';
        }
        
        const abstractText = book.abstract || '暂无简介';
        const needsExpand = abstractText.length > 100;
        
        item.innerHTML = `
            <img class="search-cover" src="${book.cover_url || ''}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none'">
            <div class="search-info">
                <div class="search-title">
                    ${book.book_name}
                    ${status ? `<span class="status-badge ${statusClass}">${displayStatus}</span>` : ''}
                </div>
                <div class="search-meta">${book.author} · ${wordCount}${chapterCount ? ' · ' + chapterCount : ''}</div>
                <div class="search-desc-wrapper">
                    <div class="search-desc ${needsExpand ? 'collapsed' : ''}">${abstractText}</div>
                    ${needsExpand ? `<button class="desc-toggle" type="button" data-action="toggle-desc"><iconify-icon icon="line-md:chevron-small-down"></iconify-icon></button>` : ''}
                </div>
            </div>
            <div class="search-actions">
                <button class="btn btn-sm btn-primary" type="button" data-action="add-queue">添加到队列</button>
            </div>
        `;

        fragment.appendChild(item);
    });
    
    // 插入到加载更多按钮之前
    listContainer.insertBefore(fragment, loadMoreContainer);
    
    // 显示/隐藏加载更多按钮
    loadMoreContainer.style.display = hasMore ? 'block' : 'none';
    
    // 更新计数
    const totalCount = listContainer.querySelectorAll('.search-item').length;
    countSpan.textContent = `找到 ${totalCount} 本`;
}

function selectBook(bookId, bookName) {
    document.getElementById('bookId').value = bookId;
    logger.logKey('log_selected', bookName, bookId);
    
    // 自动切换到下载标签页
    switchTab('download');
}

function clearSearchResults() {
    document.getElementById('searchHeader').style.display = 'none';
    const listContainer = document.getElementById('searchResultList');
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    listContainer.innerHTML = '';
    loadMoreContainer.style.display = 'none';
    listContainer.appendChild(loadMoreContainer);
    document.getElementById('searchKeyword').value = '';
    searchOffset = 0;
    currentSearchKeyword = '';
    searchBookCache.clear();
}

async function handleSelectChapters() {
    const bookId = document.getElementById('bookId').value.trim();
    if (!bookId) {
        Toast.warning('请输入书籍ID');
        return;
    }
    
    // 验证bookId (简单复用验证逻辑)
    let validId = bookId;
    if (bookId.includes('fanqienovel.com')) {
        const match = bookId.match(/\/page\/(\d+)/);
        if (match) validId = match[1];
        else { Toast.error('URL格式不正确，请检查链接'); return; }
    } else if (!/^\d+$/.test(bookId)) {
        Toast.error('书籍ID必须是数字');
        return;
    }
    
    const modal = document.getElementById('chapterModal');
    const listContainer = document.getElementById('chapterList');
    
    modal.style.display = 'flex';
    listContainer.innerHTML = `<div style="text-align: center; padding: 20px;">正在加载章节列表...</div>`;
    
    logger.logKey('log_get_chapter_list', validId);
    const bookInfo = await api.getBookInfo(validId);
    
    if (bookInfo && bookInfo.chapters) {
        currentChapters = bookInfo.chapters;
        renderChapterList(bookInfo.chapters);
    } else {
        listContainer.innerHTML = `<div style="text-align: center; padding: 20px; color: red;">获取章节列表失败</div>`;
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
    document.getElementById('selectedCount').textContent = `已选择 ${checked.length}/${checkboxes.length} 章`;
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
            btn.textContent = `已选 ${AppState.selectedChapters.length} 章`;
            btn.classList.remove('btn-info');
            btn.classList.add('btn-success');
            logger.logKey('log_confirmed_selection', AppState.selectedChapters.length);
        } else {
            btn.textContent = '选择章节';
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
    if (!markdown) return '暂无更新日志';
    
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
    updateDescription.style.display = 'block';
    versionSelector.style.display = 'none';
    downloadUpdateBtn.disabled = false;
    downloadUpdateBtn.textContent = '下载更新';
    
    const modalFooter = document.querySelector('.modal-footer');
    if (modalFooter) modalFooter.style.display = 'flex';
    
    const progressContainer = document.getElementById('updateProgressContainer');
    if (progressContainer) progressContainer.style.display = 'none';
    
    currentVersion.textContent = updateInfo.current_version;
    latestVersion.textContent = updateInfo.latest_version;
    
    const releaseBody = updateInfo.release_info?.body || updateInfo.message || '暂无更新日志';
    updateDescription.innerHTML = simpleMarkdownToHtml(releaseBody);
    
    // 获取可下载的版本选项
    try {
        const response = await fetch('/api/get-update-assets', {
            headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
        });
        const result = await response.json();
        
        if (result.success && result.assets && result.assets.length > 0) {
            // 显示版本选择器
            versionSelector.innerHTML = `<h4>选择版本</h4>`;
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
                
                let typeText = '标准版';
                if (asset.type === 'standalone') typeText = '独立版';
                else if (asset.type === 'debug') typeText = '调试版';
                
                const label = document.createElement('span');
                label.innerHTML = `
                    <strong>${typeText}</strong> 
                    (${asset.size_mb} MB)
                    ${asset.recommended ? `<span class="badge">推荐</span>` : ''}
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
                    Toast.warning('请选择版本');
                    return;
                }
                
                const downloadUrl = selectedRadio.value;
                const filename = selectedRadio.dataset.filename;
                
                if (canAutoUpdate) {
                    // 自动更新流程 (支持 Windows/Linux/macOS)
                    downloadUpdateBtn.disabled = true;
                    downloadUpdateBtn.textContent = '下载中...';
                    
                    // 下载开始后禁止关闭弹窗
                    if (modal.setDownloading) modal.setDownloading(true);
                    
                    // 隐藏不需要的元素以腾出空间
                    updateDescription.style.display = 'none'; // 隐藏更新说明
                    versionSelector.style.display = 'none'; // 隐藏版本选择
                    
                    // 创建或显示进度条
                    let progressContainer = document.getElementById('updateProgressContainer');
                    if (!progressContainer) {
                        progressContainer = document.createElement('div');
                        progressContainer.id = 'updateProgressContainer';
                        progressContainer.innerHTML = `
                            <div class="update-progress-card">
                                <h4 class="update-progress-title">下载进度</h4>
                                <div class="update-progress-info">
                                    <span id="updateProgressText">正在连接...</span>
                                    <span id="updateProgressPercent">0%</span>
                                </div>
                                <div class="multi-thread-progress" id="multiThreadProgress">
                                </div>
                                <div id="threadInfo" class="thread-info"></div>
                                <div class="update-progress-hint">
                                    下载进行中，请勿关闭窗口
                                </div>
                            </div>
                        `;
                        // 插入到更新信息区域
                        const updateInfo = document.querySelector('.update-info');
                        if (updateInfo) {
                            updateInfo.appendChild(progressContainer);
                        } else {
                            versionSelector.parentNode.insertBefore(progressContainer, versionSelector.nextSibling);
                        }
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
                        
                        // 初始化进度条显示
                        const multiProgress = document.getElementById('multiThreadProgress');
                        if (multiProgress) {
                            multiProgress.innerHTML = `<div class="thread-segment" style="width:100%;background:linear-gradient(to right, #3b82f6 0%, rgba(255,255,255,0.1) 0%);"></div>`;
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
                                
                                if (status.merging) {
                                    // 正在合并文件
                                    const multiProgress = document.getElementById('multiThreadProgress');
                                    const threadInfo = document.getElementById('threadInfo');
                                    multiProgress.innerHTML = `<div class="thread-segment" style="width:100%;background:linear-gradient(90deg, #f59e0b 0%, #fbbf24 50%, #f59e0b 100%);animation:merging-pulse 1.5s ease-in-out infinite;"></div>`;
                                    threadInfo.textContent = '正在合并文件...';
                                    progressText.textContent = '正在合并文件...';
                                    progressPercent.textContent = '100%';
                                    setTimeout(pollProgress, 300);
                                } else if (status.is_downloading) {
                                    // 更新多线程进度条
                                    const multiProgress = document.getElementById('multiThreadProgress');
                                    const threadInfo = document.getElementById('threadInfo');
                                    
                                    if (status.thread_progress && status.thread_progress.length > 0 && status.total_size > 0) {
                                        const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
                                        let html = '';
                                        status.thread_progress.forEach((tp, idx) => {
                                            const color = colors[idx % colors.length];
                                            const width = status.total_size > 0 ? (tp.total / status.total_size) * 100 : (100 / status.thread_progress.length);
                                            const filled = tp.percent || 0;
                                            html += `<div class="thread-segment" style="width:${width}%;background:linear-gradient(to right, ${color} ${filled}%, rgba(255,255,255,0.1) ${filled}%);"></div>`;
                                        });
                                        multiProgress.innerHTML = html;
                                        threadInfo.textContent = `${status.thread_count || 1} 线程`;
                                    } else {
                                        // 单线程或无法获取文件大小时显示单色进度条
                                        multiProgress.innerHTML = `<div class="thread-segment" style="width:100%;background:linear-gradient(to right, #3b82f6 ${status.progress}%, rgba(255,255,255,0.1) ${status.progress}%);"></div>`;
                                        threadInfo.textContent = status.thread_count > 1 ? `${status.thread_count} 线程` : '';
                                    }
                                    
                                    progressText.textContent = status.message || '下载中...';
                                    progressPercent.textContent = status.progress + '%';
                                    setTimeout(pollProgress, 300);
                                } else if (status.completed) {
                                    const multiProgress = document.getElementById('multiThreadProgress');
                                    multiProgress.innerHTML = `<div class="thread-segment" style="width:100%;background:#10b981;"></div>`;
                                    progressText.textContent = '下载完成';
                                    progressPercent.textContent = '100%';
                                    
                                    // 下载完成后，将原来的下载按钮变成安装按钮
                                    downloadUpdateBtn.disabled = false;
                                    downloadUpdateBtn.textContent = '安装更新';
                                    downloadUpdateBtn.onclick = async () => {
                                        downloadUpdateBtn.disabled = true;
                                        downloadUpdateBtn.textContent = '准备中...';
                                        
                                        try {
                                            const applyRes = await fetch('/api/apply-update', { 
                                                method: 'POST',
                                                headers: AppState.accessToken ? { 'X-Access-Token': AppState.accessToken } : {}
                                            });
                                            const applyResult = await applyRes.json();
                                            
                                            if (applyResult.success) {
                                                downloadUpdateBtn.textContent = '重启中...';
                                                progressText.textContent = applyResult.message;
                                            } else {
                                                Toast.error('应用更新失败: ' + applyResult.message);
                                                downloadUpdateBtn.disabled = false;
                                                downloadUpdateBtn.textContent = '安装更新';
                                            }
                                        } catch (e) {
                                            Toast.error('应用更新失败: ' + e.message);
                                            downloadUpdateBtn.disabled = false;
                                            downloadUpdateBtn.textContent = '安装更新';
                                        }
                                    };
                                } else if (status.error) {
                                    progressText.textContent = status.message;
                                    downloadUpdateBtn.disabled = false;
                                    downloadUpdateBtn.textContent = '重试';
                                } else {
                                    // 初始状态或等待状态，继续轮询
                                    if (!status.is_downloading && !status.completed && !status.error) {
                                        progressText.textContent = status.message || '准备下载...';
                                    }
                                    setTimeout(pollProgress, 300);
                                }
                            } catch (e) {
                                console.error('获取下载状态失败:', e);
                                setTimeout(pollProgress, 1000);
                            }
                        };
                        
                        setTimeout(pollProgress, 500);
                        
                    } catch (e) {
                        Toast.error('下载失败: ' + e.message);
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
    
    // 用于跟踪是否正在下载更新
    let isUpdateDownloading = false;
    
    const tryCloseModal = () => {
        if (isUpdateDownloading) {
            Toast.warning('下载进行中，请勿关闭');
            return;
        }
        modal.style.display = 'none';
    };
    
    closeUpdateBtn.onclick = tryCloseModal;
    updateModalClose.onclick = tryCloseModal;
    
    modal.onclick = (e) => {
        if (e.target === modal) {
            tryCloseModal();
        }
    };
    
    // 暴露设置下载状态的方法
    modal.setDownloading = (value) => {
        isUpdateDownloading = value;
        if (value) {
            closeUpdateBtn.style.display = 'none';
            updateModalClose.style.display = 'none';
        } else {
            closeUpdateBtn.style.display = '';
            updateModalClose.style.display = '';
        }
    };
}

async function handleAddToQueue(bookIdOverride = null, prefill = null) {
    const bookId = (bookIdOverride ?? document.getElementById('bookId').value).trim();

    if (!bookId) {
        Toast.warning('请输入书籍ID');
        return;
    }

    // 验证 bookId 格式并标准化为纯数字 ID
    let normalizedId = bookId;
    if (bookId.includes('fanqienovel.com')) {
        const match = bookId.match(/\/page\/(\d+)/);
        if (!match) {
            Toast.error('URL格式不正确');
            return;
        }
        normalizedId = match[1];
    } else if (!/^\d+$/.test(bookId)) {
        Toast.error('书籍ID必须是数字');
        return;
    }

    logger.logKey('log_prepare_download', normalizedId);
    
    // 切换到下载标签页以显示内嵌确认区域
    switchTab('download');
    
    showInlineConfirm(normalizedId, prefill);
}

// 内嵌确认区域状态
const InlineConfirmState = {
    loading: true,
    error: null,
    bookInfo: null,
    chapters: [],
    bookId: null,
    prefill: null
};

function showInlineConfirm(bookId, prefill = null) {
    try {
        const container = document.getElementById('inlineConfirmContainer');
        if (!container) return;

        // 保存状态
        InlineConfirmState.bookId = bookId;
        InlineConfirmState.prefill = prefill;
        InlineConfirmState.loading = true;
        InlineConfirmState.error = null;
        InlineConfirmState.bookInfo = null;
        InlineConfirmState.chapters = [];

        // 显示容器
        container.style.display = 'block';

        // Elements
        const coverEl = document.getElementById('inlineCover');
        const titleEl = document.getElementById('inlineBookTitle');
        const authorEl = document.getElementById('inlineBookAuthor');
        const abstractEl = document.getElementById('inlineBookAbstract');
        const chaptersEl = document.getElementById('inlineBookChapters');

        const loadingHint = document.getElementById('inlineChapterLoadingHint');
        const loadingText = document.getElementById('inlineChapterLoadingText');

        const chapterInputs = document.getElementById('inlineChapterInputs');
        const startSelect = document.getElementById('inlineStartChapter');
        const endSelect = document.getElementById('inlineEndChapter');

        const quickRangeContainer = document.getElementById('inlineChapterQuickRange');
        const quickRangeInput = document.getElementById('inlineQuickRangeInput');
        const quickRangeResult = document.getElementById('inlineQuickRangeResult');

        const manualContainer = document.getElementById('inlineChapterManualContainer');
        const manualList = document.getElementById('inlineChapterList');
        const selectedCountEl = document.getElementById('inlineSelectedCount');

        const confirmBtn = document.getElementById('inlineConfirmAddQueueBtn');
        const cancelBtn = document.getElementById('inlineCancelBtn');

        // Reset radio buttons
        const allRadio = container.querySelector('input[name="inlineChapterMode"][value="all"]');
        if (allRadio) allRadio.checked = true;

        // Prefill (search results / user input)
        const preTitle = prefill?.book_name || bookId;
        const preAuthor = prefill?.author ? `作者: ${prefill.author}` : '正在获取书籍信息...';
        titleEl.textContent = preTitle;
        authorEl.textContent = preAuthor;
        abstractEl.textContent = prefill?.abstract || '';
        chaptersEl.textContent = prefill?.chapter_count ? `共 ${prefill.chapter_count} 章` : '';

        const coverUrl = prefill?.cover_url || '';
        if (coverUrl) {
            coverEl.src = coverUrl;
            coverEl.style.display = '';
            coverEl.onerror = () => { coverEl.style.display = 'none'; };
        } else {
            coverEl.style.display = 'none';
        }

        const getMode = () => container.querySelector('input[name="inlineChapterMode"]:checked')?.value || 'all';

        const setHint = (text, showSpinner = true) => {
            if (!text) {
                loadingHint.style.display = 'none';
                return;
            }
            loadingHint.style.display = 'flex';
            loadingText.textContent = text;
            loadingHint.classList.toggle('is-error', !showSpinner);
            const icon = loadingHint.querySelector('iconify-icon');
            if (icon) icon.style.display = showSpinner ? 'inline-block' : 'none';
        };

        const updateSelectedCount = () => {
            const checked = manualList.querySelectorAll('input[type="checkbox"]:checked').length;
            selectedCountEl.textContent = `已选 ${checked} 项`;
        };

        const renderChaptersControls = () => {
            const chapters = InlineConfirmState.chapters || [];

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

            // Manual list with Shift select and drag select support
            manualList.innerHTML = '';
            let lastClickedIndex = -1;
            let isDragging = false;
            let dragStartIndex = -1;
            let dragSelectState = true; // true = select, false = deselect
            let originalStates = []; // 保存拖动开始前的状态

            // 选择范围的辅助函数
            const selectRange = (start, end, state) => {
                const checkboxes = manualList.querySelectorAll('input[type="checkbox"]');
                const minIdx = Math.min(start, end);
                const maxIdx = Math.max(start, end);
                // 先恢复原始状态
                checkboxes.forEach((cb, i) => {
                    cb.checked = originalStates[i] || false;
                });
                // 再设置范围内的状态
                for (let i = minIdx; i <= maxIdx; i++) {
                    checkboxes[i].checked = state;
                }
            };

            chapters.forEach((ch, idx) => {
                const label = document.createElement('label');
                label.className = 'chapter-item';
                label.dataset.index = idx;
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.value = String(idx);

                // Shift + Click for range selection
                label.addEventListener('click', (e) => {
                    if (e.target === checkbox) return;
                    
                    e.preventDefault();
                    const currentIndex = idx;
                    
                    if (e.shiftKey && lastClickedIndex !== -1) {
                        // Shift+Click: select range
                        const start = Math.min(lastClickedIndex, currentIndex);
                        const end = Math.max(lastClickedIndex, currentIndex);
                        const checkboxes = manualList.querySelectorAll('input[type="checkbox"]');
                        for (let i = start; i <= end; i++) {
                            checkboxes[i].checked = true;
                        }
                    } else {
                        // Normal click: toggle
                        checkbox.checked = !checkbox.checked;
                    }
                    lastClickedIndex = currentIndex;
                    updateSelectedCount();
                });

                // Drag selection - mousedown
                label.addEventListener('mousedown', (e) => {
                    if (e.target === checkbox) return;
                    // 保存当前所有checkbox的状态
                    const checkboxes = manualList.querySelectorAll('input[type="checkbox"]');
                    originalStates = Array.from(checkboxes).map(cb => cb.checked);
                    
                    isDragging = true;
                    dragStartIndex = idx;
                    dragSelectState = !checkbox.checked;
                    // 立即选中/取消当前项
                    checkbox.checked = dragSelectState;
                    e.preventDefault();
                    updateSelectedCount();
                });

                // Drag selection - mouseenter: 选择从起点到当前的范围
                label.addEventListener('mouseenter', () => {
                    if (isDragging && dragStartIndex !== -1) {
                        selectRange(dragStartIndex, idx, dragSelectState);
                        updateSelectedCount();
                    }
                });

                checkbox.addEventListener('change', updateSelectedCount);

                const span = document.createElement('span');
                span.textContent = ch.title || `${idx + 1}`;

                label.appendChild(checkbox);
                label.appendChild(span);
                manualList.appendChild(label);
            });

            // Global mouseup to end drag
            const handleMouseUp = () => {
                if (isDragging) {
                    isDragging = false;
                    dragStartIndex = -1;
                    originalStates = [];
                    updateSelectedCount();
                }
            };
            document.addEventListener('mouseup', handleMouseUp, { once: false });
            manualList._cleanupDrag = () => document.removeEventListener('mouseup', handleMouseUp);

            updateSelectedCount();
        };

        const showLoadingChapters = () => {
            startSelect.disabled = true;
            endSelect.disabled = true;
            startSelect.innerHTML = '';
            endSelect.innerHTML = '';
            manualList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-text">正在加载章节列表...</div>
                </div>
            `;
            selectedCountEl.textContent = `已选 0 项`;
        };

        const updateModeUI = () => {
            const mode = getMode();
            chapterInputs.style.display = mode === 'range' ? 'grid' : 'none';
            quickRangeContainer.style.display = mode === 'quick' ? 'block' : 'none';
            manualContainer.style.display = mode === 'manual' ? 'block' : 'none';

            // 无论哪种模式，加载中或出错时都禁用确认按钮
            if (InlineConfirmState.loading) {
                if (mode !== 'all') {
                    setHint('正在加载章节列表...', true);
                    showLoadingChapters();
                } else {
                    setHint('正在获取书籍信息...', true);
                }
                confirmBtn.disabled = true;
                return;
            }

            if (InlineConfirmState.error) {
                setHint(InlineConfirmState.error, false);
                confirmBtn.disabled = true;
                return;
            }

            setHint('');
            confirmBtn.disabled = false;
        };

        // Remove old event listeners by cloning elements
        const cloneAndReplace = (selector) => {
            const el = container.querySelector(selector);
            if (el) {
                const clone = el.cloneNode(true);
                el.parentNode.replaceChild(clone, el);
                return clone;
            }
            return null;
        };

        // Mode change handlers
        container.querySelectorAll('input[name="inlineChapterMode"]').forEach(input => {
            const clone = input.cloneNode(true);
            input.parentNode.replaceChild(clone, input);
            clone.addEventListener('change', updateModeUI);
        });

        // Manual action buttons
        const selectAllBtn = cloneAndReplace('#inlineSelectAllBtn');
        const selectNoneBtn = cloneAndReplace('#inlineSelectNoneBtn');
        const selectInvertBtn = cloneAndReplace('#inlineSelectInvertBtn');

        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => {
                manualList.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
                updateSelectedCount();
            });
        }
        if (selectNoneBtn) {
            selectNoneBtn.addEventListener('click', () => {
                manualList.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
                updateSelectedCount();
            });
        }
        if (selectInvertBtn) {
            selectInvertBtn.addEventListener('click', () => {
                manualList.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = !cb.checked);
                updateSelectedCount();
            });
        }

        // Quick range apply button
        const applyQuickRangeBtn = cloneAndReplace('#inlineApplyQuickRangeBtn');
        if (applyQuickRangeBtn) {
            applyQuickRangeBtn.addEventListener('click', async () => {
                const inputValue = quickRangeInput.value.trim();
                if (!inputValue) {
                    Toast.warning('请输入章节范围');
                    return;
                }

                const chapters = InlineConfirmState.chapters || [];
                if (chapters.length === 0) {
                    Toast.warning('正在加载章节列表...');
                    return;
                }

                try {
                    const headers = { 'Content-Type': 'application/json' };
                    if (AppState.accessToken) {
                        headers['X-Access-Token'] = AppState.accessToken;
                    }
                    const response = await fetch('/api/parse-chapter-range', {
                        method: 'POST',
                        headers,
                        body: JSON.stringify({
                            input: inputValue,
                            max_chapter: chapters.length
                        })
                    });
                    const result = await response.json();

                    if (result.success && result.data && result.data.chapters.length > 0) {
                        // 切换到手动模式并选中对应章节
                        const manualRadio = container.querySelector('input[name="inlineChapterMode"][value="manual"]');
                        if (manualRadio) {
                            manualRadio.checked = true;
                            chapterInputs.style.display = 'none';
                            quickRangeContainer.style.display = 'none';
                            manualContainer.style.display = 'block';

                            // 选中解析出的章节
                            const checkboxes = manualList.querySelectorAll('input[type="checkbox"]');
                            const selectedSet = new Set(result.data.chapters);
                            checkboxes.forEach(cb => {
                                cb.checked = selectedSet.has(parseInt(cb.value));
                            });
                            updateSelectedCount();

                            Toast.success(`已应用范围，选中 ${result.data.chapters.length} 章`);
                        }

                        // 显示警告
                        if (result.data.warnings && result.data.warnings.length > 0) {
                            quickRangeResult.innerHTML = `<span style="color: #ffaa00;">⚠️ ${result.data.warnings.join('; ')}</span>`;
                        } else {
                            quickRangeResult.innerHTML = `<span style="color: #00ff00;">✓ 已选中 ${result.data.chapters.length} 章</span>`;
                        }
                    } else {
                        const errorMsg = result.data?.errors?.join('; ') || result.message || '解析失败';
                        quickRangeResult.innerHTML = `<span style="color: #ff4444;">✗ ${errorMsg}</span>`;
                        Toast.error(errorMsg);
                    }
                } catch (e) {
                    quickRangeResult.innerHTML = `<span style="color: #ff4444;">✗ ${e.message}</span>`;
                    Toast.error(e.message);
                }
            });
        }

        // Cancel button
        const newCancelBtn = cloneAndReplace('#inlineCancelBtn');
        if (newCancelBtn) {
            newCancelBtn.addEventListener('click', hideInlineConfirm);
        }

        // Confirm button
        const newConfirmBtn = cloneAndReplace('#inlineConfirmAddQueueBtn');
        if (newConfirmBtn) {
            newConfirmBtn.addEventListener('click', async () => {
                const mode = getMode();

                let startChapter = null;
                let endChapter = null;
                let selectedChapters = null;

                if (mode === 'range') {
                    if (InlineConfirmState.loading) {
                        updateModeUI();
                        return;
                    }
                    const startIdx = parseInt(startSelect.value, 10);
                    const endIdx = parseInt(endSelect.value, 10);
                    if (Number.isNaN(startIdx) || Number.isNaN(endIdx) || startIdx > endIdx) {
                        Toast.error('章节范围错误');
                        return;
                    }
                    startChapter = startIdx + 1;
                    endChapter = endIdx + 1;
                    logger.logKey('log_chapter_range', startChapter, endChapter);
                } else if (mode === 'quick') {
                    // 快速范围模式：解析输入并转换为 selected_chapters
                    if (InlineConfirmState.loading) {
                        updateModeUI();
                        return;
                    }
                    const inputValue = quickRangeInput.value.trim();
                    if (!inputValue) {
                        Toast.warning('请输入章节范围');
                        return;
                    }

                    const chapters = InlineConfirmState.chapters || [];
                    try {
                        const headers = { 'Content-Type': 'application/json' };
                        if (AppState.accessToken) {
                            headers['X-Access-Token'] = AppState.accessToken;
                        }
                        const response = await fetch('/api/parse-chapter-range', {
                            method: 'POST',
                            headers,
                            body: JSON.stringify({
                                input: inputValue,
                                max_chapter: chapters.length
                            })
                        });
                        const result = await response.json();

                        if (result.success && result.data && result.data.chapters.length > 0) {
                            selectedChapters = result.data.chapters;
                            logger.logKey('log_mode_manual', selectedChapters.length);
                        } else {
                            const errorMsg = result.data?.errors?.join('; ') || result.message || '解析失败';
                            Toast.error(errorMsg);
                            return;
                        }
                    } catch (e) {
                        Toast.error(e.message);
                        return;
                    }
                } else if (mode === 'manual') {
                    if (InlineConfirmState.loading) {
                        updateModeUI();
                        return;
                    }
                    selectedChapters = Array.from(manualList.querySelectorAll('input[type="checkbox"]:checked'))
                        .map(cb => parseInt(cb.value, 10))
                        .filter(n => !Number.isNaN(n));

                    if (selectedChapters.length === 0) {
                        Toast.warning('请至少选择一个章节');
                        return;
                    }
                    logger.logKey('log_mode_manual', selectedChapters.length);
                }

                // 检查重复下载
                const info = InlineConfirmState.bookInfo;
                const currentBookId = info?.book_id || bookId;
                try {
                    const headers = { 'Content-Type': 'application/json' };
                    if (AppState.accessToken) {
                        headers['X-Access-Token'] = AppState.accessToken;
                    }
                    const historyResponse = await fetch('/api/download-history/check', {
                        method: 'POST',
                        headers,
                        body: JSON.stringify({ book_id: currentBookId })
                    });
                    const historyResult = await historyResponse.json();

                    if (historyResult.success && historyResult.exists) {
                        const record = historyResult.record;
                        const downloadTime = new Date(record.download_time).toLocaleString();

                        // 显示重复下载确认对话框
                        const action = await showDuplicateDownloadDialog(info || { book_id: currentBookId, book_name: preTitle }, record, downloadTime);

                        if (action === 'cancel') {
                            return;
                        } else if (action === 'open') {
                            // 打开已有文件所在目录
                            if (record.save_path) {
                                try {
                                    await fetch('/api/open-folder', {
                                        method: 'POST',
                                        headers,
                                        body: JSON.stringify({ path: record.save_path })
                                    });
                                } catch (e) {
                                    Toast.info('文件路径: ' + record.save_path);
                                }
                            }
                            return;
                        }
                        // action === 'continue' 继续添加到队列
                    }
                } catch (e) {
                    // 检查失败不阻止下载
                    console.warn('Download history check failed:', e);
                }

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
                hideInlineConfirm();
                switchTab('queue');
            });
        }

        // Initial mode UI
        updateModeUI();

        // Start fetching book info & chapters
        (async () => {
            showLoadingChapters();
            try {
                const info = await api.getBookInfo(bookId);
                if (!info) {
                    InlineConfirmState.loading = false;
                    InlineConfirmState.error = '获取章节列表失败';
                    updateModeUI();
                    return;
                }

                InlineConfirmState.bookInfo = info;
                InlineConfirmState.chapters = Array.isArray(info.chapters) ? info.chapters : [];
                InlineConfirmState.loading = false;
                InlineConfirmState.error = null;

                // Update book info block
                titleEl.textContent = info.book_name || preTitle;
                authorEl.textContent = `作者: ${info.author || prefill?.author || ''}`;
                abstractEl.textContent = info.abstract || prefill?.abstract || '';
                chaptersEl.textContent = `共 ${InlineConfirmState.chapters.length} 章`;

                if (info.cover_url) {
                    coverEl.src = info.cover_url;
                    coverEl.style.display = '';
                    coverEl.onerror = () => { coverEl.style.display = 'none'; };
                }

                renderChaptersControls();
                updateModeUI();
            } catch (e) {
                InlineConfirmState.loading = false;
                InlineConfirmState.error = e?.message || '获取章节列表失败';
                updateModeUI();
            }
        })();
    } catch (e) {
        console.error('Error showing inline confirm:', e);
        logger.logKey('log_show_dialog_fail', e.message);
        Toast.error('显示对话框失败');
    }
}

function hideInlineConfirm() {
    const container = document.getElementById('inlineConfirmContainer');
    if (container) {
        container.style.display = 'none';
    }
    // Clear input
    const bookIdInput = document.getElementById('bookId');
    if (bookIdInput) {
        bookIdInput.value = '';
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
                <p style="margin: 0 0 8px 0; color: #00ff00; font-family: 'Press Start 2P', monospace; font-size: 11px;">已选择 ${AppState.selectedChapters.length} 章</p>
                <p style="margin: 0 0 10px 0; color: #008800; font-size: 10px;">手动选择模式</p>
                <button class="btn btn-sm btn-secondary" onclick="window.reSelectChapters()">重新选择</button>
            </div>
        `;
    } else {
        selectionHtml = `
            <div class="chapter-range">
                <label>
                    <input type="radio" name="chapterMode" value="all" checked>
                    全部章节
                </label>
                <label>
                    <input type="radio" name="chapterMode" value="range">
                    章节范围
                </label>
                <label>
                    <input type="radio" name="chapterMode" value="quick">
                    快速范围输入
                </label>
                <label>
                    <input type="radio" name="chapterMode" value="manual">
                    手动选择
                </label>
            </div>
            
            <div class="chapter-inputs" id="chapterInputs" style="display: none;">
                <div class="input-row">
                    <label>起始章节</label>
                    <select id="startChapter" class="chapter-select">
                        ${bookInfo.chapters.map((ch, idx) => 
                            `<option value="${idx}">${ch.title}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="input-row">
                    <label>结束章节</label>
                    <select id="endChapter" class="chapter-select">
                        ${bookInfo.chapters.map((ch, idx) => 
                            `<option value="${idx}" ${idx === bookInfo.chapters.length - 1 ? 'selected' : ''}>${ch.title}</option>`
                        ).join('')}
                    </select>
                </div>
            </div>
            
            <div class="chapter-quick-range" id="chapterQuickRange" style="display: none; margin-top: 12px;">
                <div class="input-row" style="margin-bottom: 8px;">
                    <label>章节范围</label>
                    <input type="text" id="quickRangeInput" class="form-input" 
                           placeholder="例如: 1-100, 150, 200-300"
                           style="width: 100%; font-family: monospace;">
                </div>
                <div class="quick-range-hint" style="font-size: 11px; color: #888; margin-bottom: 8px;">
                    支持格式: 单个数字(5)、范围(1-100)、多个范围(1-10, 50-100)
                </div>
                <div id="quickRangeResult" style="font-size: 12px; min-height: 20px;"></div>
                <button class="btn btn-sm btn-secondary" id="applyQuickRangeBtn" style="margin-top: 8px;">
                    应用范围
                </button>
            </div>
            
            <div class="chapter-manual-container" id="chapterManualContainer" style="display: none; margin-top: 12px;">
                <div class="chapter-actions" style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 2px solid #006600; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <button class="btn btn-sm btn-secondary" onclick="window.selectAllChaptersInDialog()">全选</button>
                    <button class="btn btn-sm btn-secondary" onclick="window.selectNoneChaptersInDialog()">全不选</button>
                    <button class="btn btn-sm btn-secondary" onclick="window.invertChaptersInDialog()">反选</button>
                    <span id="dialogSelectedCount" style="margin-left: 15px; font-weight: bold;">已选 0 项</span>
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
                <h3>确认下载</h3>
                <button class="modal-close" onclick="this.closest('.modal').remove()">×</button>
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
                <button class="btn btn-primary" id="confirmDownloadBtn">添加到队列</button>
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
        const chapterQuickRange = modal.querySelector('#chapterQuickRange');
        
        chapterModeInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                chapterInputs.style.display = e.target.value === 'range' ? 'block' : 'none';
                chapterManualContainer.style.display = e.target.value === 'manual' ? 'block' : 'none';
                if (chapterQuickRange) {
                    chapterQuickRange.style.display = e.target.value === 'quick' ? 'block' : 'none';
                }
            });
        });
        
        // 快速范围输入事件
        const quickRangeInput = modal.querySelector('#quickRangeInput');
        const quickRangeResult = modal.querySelector('#quickRangeResult');
        const applyQuickRangeBtn = modal.querySelector('#applyQuickRangeBtn');
        
        if (quickRangeInput && quickRangeResult) {
            let debounceTimer = null;
            quickRangeInput.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(async () => {
                    const inputValue = quickRangeInput.value.trim();
                    if (!inputValue) {
                        quickRangeResult.innerHTML = '';
                        return;
                    }
                    
                    try {
                        const headers = { 'Content-Type': 'application/json' };
                        if (AppState.accessToken) {
                            headers['X-Access-Token'] = AppState.accessToken;
                        }
                        const response = await fetch('/api/parse-chapter-range', {
                            method: 'POST',
                            headers,
                            body: JSON.stringify({
                                input: inputValue,
                                max_chapter: bookInfo.chapters.length
                            })
                        });
                        const result = await response.json();
                        
                        if (result.success && result.data) {
                            const { chapters, errors, warnings } = result.data;
                            let html = '';
                            
                            if (errors.length > 0) {
                                html += `<span style="color: #ff4444;">❌ ${errors.join(', ')}</span>`;
                            } else if (chapters.length > 0) {
                                html += `<span style="color: #00ff00;">✓ 已选择 ${chapters.length} 章</span>`;
                            }
                            
                            if (warnings.length > 0) {
                                html += `<br><span style="color: #ffaa00;">⚠ ${warnings.join(', ')}</span>`;
                            }
                            
                            quickRangeResult.innerHTML = html;
                        } else {
                            quickRangeResult.innerHTML = `<span style="color: #ff4444;">❌ ${result.message || '解析失败'}</span>`;
                        }
                    } catch (e) {
                        quickRangeResult.innerHTML = `<span style="color: #ff4444;">❌ 解析失败</span>`;
                    }
                }, 300);
            });
        }
        
        if (applyQuickRangeBtn) {
            applyQuickRangeBtn.addEventListener('click', async () => {
                const inputValue = quickRangeInput.value.trim();
                if (!inputValue) {
                    Toast.warning('请输入章节范围');
                    return;
                }
                
                try {
                    const headers = { 'Content-Type': 'application/json' };
                    if (AppState.accessToken) {
                        headers['X-Access-Token'] = AppState.accessToken;
                    }
                    const response = await fetch('/api/parse-chapter-range', {
                        method: 'POST',
                        headers,
                        body: JSON.stringify({
                            input: inputValue,
                            max_chapter: bookInfo.chapters.length
                        })
                    });
                    const result = await response.json();
                    
                    if (result.success && result.data && result.data.chapters.length > 0) {
                        // 切换到手动模式并选中对应章节
                        const manualRadio = modal.querySelector('input[name="chapterMode"][value="manual"]');
                        if (manualRadio) {
                            manualRadio.checked = true;
                            chapterInputs.style.display = 'none';
                            chapterQuickRange.style.display = 'none';
                            chapterManualContainer.style.display = 'block';
                            
                            // 选中解析出的章节
                            const checkboxes = modal.querySelectorAll('#dialogChapterList input[type="checkbox"]');
                            const selectedSet = new Set(result.data.chapters);
                            checkboxes.forEach(cb => {
                                cb.checked = selectedSet.has(parseInt(cb.value));
                            });
                            window.updateDialogSelectedCount();
                            
                            Toast.success(`已应用范围，选中 ${result.data.chapters.length} 章`);
                        }
                    } else if (result.data && result.data.errors.length > 0) {
                        Toast.error(result.data.errors.join(', '));
                    } else {
                        Toast.warning('没有选中任何章节');
                    }
                } catch (e) {
                    Toast.error('解析范围失败');
                }
            });
        }
    }
    
    modal.querySelector('#confirmDownloadBtn').addEventListener('click', async () => {
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
                        Toast.error('章节范围错误');
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
                        Toast.warning('请至少选择一个章节');
                        return;
                    }
                    
                    logger.logKey('log_prepare_download', bookInfo.book_name);
                    logger.logKey('log_mode_manual', selectedChapters.length);
                } else {
                    logger.logKey('log_download_all', bookInfo.book_name);
                }
            }
        }
        
        // 检查下载历史
        try {
            const headers = { 'Content-Type': 'application/json' };
            if (AppState.accessToken) {
                headers['X-Access-Token'] = AppState.accessToken;
            }
            const historyResponse = await fetch('/api/download-history/check', {
                method: 'POST',
                headers,
                body: JSON.stringify({ book_id: bookInfo.book_id })
            });
            const historyResult = await historyResponse.json();
            
            if (historyResult.success && historyResult.exists) {
                const record = historyResult.record;
                const downloadTime = new Date(record.download_time).toLocaleString();
                
                // 显示重复下载确认对话框
                const action = await showDuplicateDownloadDialog(bookInfo, record, downloadTime);
                
                if (action === 'cancel') {
                    return;
                } else if (action === 'open') {
                    // 打开已有文件所在目录
                    if (record.save_path) {
                        try {
                            await fetch('/api/open-folder', {
                                method: 'POST',
                                headers,
                                body: JSON.stringify({ path: record.save_path })
                            });
                        } catch (e) {
                            Toast.info('文件路径: ' + record.save_path);
                        }
                    }
                    modal.remove();
                    return;
                }
                // action === 'download' 继续下载
            }
        } catch (e) {
            console.error('History check error:', e);
            // 历史检查失败不阻止下载
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
        Toast.error('显示对话框失败');
    }
}


async function handleCancel() {
    const confirmed = await ConfirmDialog.show({
        title: '确认',
        message: '确定要取消下载吗？',
        type: 'warning'
    });
    if (confirmed) {
        await api.cancelDownload();
    }
}

// 全局辅助函数 - 对话框内的章节选择
window.updateDialogSelectedCount = function() {
    const checkboxes = document.querySelectorAll('#dialogChapterList input[type="checkbox"]');
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const countElement = document.getElementById('dialogSelectedCount');
    if (countElement) {
        countElement.textContent = `已选 ${checked.length} 项`;
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

async function handleClear() {
    const confirmed = await ConfirmDialog.show({
        title: '确认',
        message: '确定要清空所有设置吗？',
        type: 'warning'
    });
    if (confirmed) {
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
    
    const selectedPath = await FolderBrowser.show({
        title: '选择保存目录',
        initialPath: currentPath
    });
    
    if (selectedPath) {
        AppState.setSavePath(selectedPath);
        logger.logKey('msg_save_path_updated', selectedPath);
    }
}

/* ===================== 初始化 ===================== */

document.addEventListener('DOMContentLoaded', async () => {
    logger.logKey('msg_app_start');
    
    // 初始化遮罩控制 - 等待节点测试完成
    const initLoadingOverlay = document.getElementById('initLoadingOverlay');
    const dashboardContainer = document.querySelector('.dashboard-container');
    
    // 检查服务是否已初始化完成（通过检查API状态）
    async function waitForInitialization() {
        const maxWaitTime = 10000; // 最大等待10秒
        const checkInterval = 500; // 每500ms检查一次
        let waitTime = 0;
        
        while (waitTime < maxWaitTime) {
            try {
                // 检查API是否可用
                const response = await fetch('/api/status');
                if (response.ok) {
                    const data = await response.json();
                    if (data.initialized || data.node_test_completed) {
                        // 初始化完成，隐藏遮罩
                        if (initLoadingOverlay) {
                            initLoadingOverlay.style.opacity = '0';
                            setTimeout(() => {
                                initLoadingOverlay.style.display = 'none';
                            }, 500);
                        }
                        if (dashboardContainer) {
                            dashboardContainer.classList.add('show');
                        }
                        return true;
                    }
                }
            } catch (error) {
                // API还未就绪，继续等待
            }
            
            // 更新加载文本
            const loadingText = document.querySelector('.init-loading-text');
            if (loadingText) {
                const elapsed = Math.floor(waitTime / 1000);
                if (elapsed < 3) {
                    loadingText.textContent = '正在测试API节点可用性和速度...';
                } else if (elapsed < 6) {
                    loadingText.textContent = '正在启动服务...';
                } else {
                    loadingText.textContent = '即将完成...';
                }
            }
            
            await new Promise(resolve => setTimeout(resolve, checkInterval));
            waitTime += checkInterval;
        }
        
        // 超时后强制显示界面
        if (initLoadingOverlay) {
            initLoadingOverlay.style.opacity = '0';
            setTimeout(() => {
                initLoadingOverlay.style.display = 'none';
            }, 500);
        }
        if (dashboardContainer) {
            dashboardContainer.classList.add('show');
        }
        return false;
    }
    
    // 开始等待初始化
    waitForInitialization();
    
    // 从URL获取访问令牌
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
        AppState.setAccessToken(token);
        logger.logKey('msg_token_loaded');
    }
    
    // 并发执行：更新检查 + 模块初始化
    const [updateResult, initSuccess] = await Promise.all([
        api.checkUpdate().catch(() => ({ success: false })),
        api.init()
    ]);
    
    // 如果有更新，显示更新弹窗，不再加载节点
    if (updateResult.success && updateResult.has_update) {
        initializeUI(true); // 跳过节点加载
        showUpdateModal(updateResult.data);
    } else {
        initializeUI(false); // 正常加载节点
        if (initSuccess) {
            logger.logKey('msg_ready');
        } else {
            logger.logKey('msg_init_partial');
            logger.logKey('msg_check_network');
        }
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
    
    // 初始化窗口拖动功能
    initWindowDrag();
}

// 窗口拖动功能
function initWindowDrag() {
    const header = document.querySelector('.dashboard-header');
    if (!header) return;
    
    const isPyWebView = () => window.pywebview && window.pywebview.api;
    
    let isDragging = false;
    
    header.addEventListener('mousedown', (e) => {
        // 忽略按钮和输入框等交互元素
        if (e.target.closest('.header-actions') || 
            e.target.closest('button') || 
            e.target.closest('input') || 
            e.target.closest('select') ||
            e.target.closest('a')) {
            return;
        }
        
        if (isPyWebView() && window.pywebview.api.start_drag) {
            isDragging = true;
            // 传入鼠标在页面内的位置（相对于窗口左上角）
            window.pywebview.api.start_drag(e.clientX, e.clientY);
            e.preventDefault();
        }
    });
    
    document.addEventListener('mousemove', (e) => {
        if (isDragging && isPyWebView() && window.pywebview.api.drag_window) {
            // 传入屏幕坐标
            window.pywebview.api.drag_window(e.screenX, e.screenY);
        }
    });
    
    document.addEventListener('mouseup', () => {
        isDragging = false;
    });
    
    // 双击标题栏最大化/还原
    header.addEventListener('dblclick', (e) => {
        if (e.target.closest('.header-actions') || 
            e.target.closest('button') || 
            e.target.closest('input') || 
            e.target.closest('select') ||
            e.target.closest('a')) {
            return;
        }
        
        if (isPyWebView()) {
            window.pywebview.api.toggle_maximize();
        }
    });
}

// 初始化窗口控制
document.addEventListener('DOMContentLoaded', initWindowControls);

/* ===================== 设置页面功能 ===================== */

class SettingsManager {
    constructor() {
        this.defaultSettings = {
            max_workers: 30,
            request_rate_limit: 0.02,
            connection_pool_size: 200,
            async_batch_size: 50,
            max_retries: 3,
            request_timeout: 30,
            api_rate_limit: 50,
            rate_limit_window: 1.0
        };
        this.currentSettings = { ...this.defaultSettings };
    }

    // 初始化设置页面
    async init() {
        await this.loadSettings();
        this.bindEvents();
        this.updateUI();
    }

    // 绑定事件
    bindEvents() {
        const saveBtn = document.getElementById('saveSettingsBtn');
        const resetBtn = document.getElementById('resetSettingsBtn');

        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveSettings());
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetSettings());
        }
    }

    // 加载设置
    async loadSettings() {
        try {
            const response = await fetch('/api/settings/get', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.settings) {
                    this.currentSettings = { ...this.defaultSettings, ...data.settings };
                }
            }
        } catch (error) {
            console.error('加载设置失败:', error);
            Toast.warning('加载设置失败,使用默认配置');
        }
    }

    // 保存设置
    async saveSettings() {
        const settings = this.getFormValues();

        // 验证设置值
        if (!this.validateSettings(settings)) {
            return;
        }

        try {
            const response = await fetch('/api/settings/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ settings })
            });

            const data = await response.json();

            if (data.success) {
                this.currentSettings = settings;
                this.showMessage('success', '设置已保存');
                Toast.success('设置已保存');
            } else {
                this.showMessage('error', data.error || '保存失败');
                Toast.error(data.error || '保存失败');
            }
        } catch (error) {
            console.error('保存设置失败:', error);
            this.showMessage('error', '保存失败');
            Toast.error('保存失败');
        }
    }

    // 重置为默认设置
    resetSettings() {
        if (confirm('确定要恢复默认设置吗?')) {
            this.currentSettings = { ...this.defaultSettings };
            this.updateUI();
            Toast.info('已恢复默认设置,请点击保存按钮');
        }
    }

    // 获取表单值
    getFormValues() {
        return {
            max_workers: parseInt(document.getElementById('setting_max_workers')?.value || this.defaultSettings.max_workers),
            request_rate_limit: parseFloat(document.getElementById('setting_request_rate_limit')?.value || this.defaultSettings.request_rate_limit),
            connection_pool_size: parseInt(document.getElementById('setting_connection_pool_size')?.value || this.defaultSettings.connection_pool_size),
            async_batch_size: parseInt(document.getElementById('setting_async_batch_size')?.value || this.defaultSettings.async_batch_size),
            max_retries: parseInt(document.getElementById('setting_max_retries')?.value || this.defaultSettings.max_retries),
            request_timeout: parseInt(document.getElementById('setting_request_timeout')?.value || this.defaultSettings.request_timeout),
            api_rate_limit: parseInt(document.getElementById('setting_api_rate_limit')?.value || this.defaultSettings.api_rate_limit),
            rate_limit_window: parseFloat(document.getElementById('setting_rate_limit_window')?.value || this.defaultSettings.rate_limit_window)
        };
    }

    // 验证设置值
    validateSettings(settings) {
        if (settings.max_workers < 1 || settings.max_workers > 100) {
            Toast.warning('最大并发数必须在1-100之间');
            return false;
        }

        if (settings.request_rate_limit < 0 || settings.request_rate_limit > 10) {
            Toast.warning('请求间隔必须在0-10秒之间');
            return false;
        }

        if (settings.connection_pool_size < 10 || settings.connection_pool_size > 500) {
            Toast.warning('连接池大小必须在10-500之间');
            return false;
        }

        if (settings.async_batch_size < 1 || settings.async_batch_size > 200) {
            Toast.warning('异步批次大小必须在1-200之间');
            return false;
        }

        if (settings.max_retries < 0 || settings.max_retries > 10) {
            Toast.warning('最大重试次数必须在0-10之间');
            return false;
        }

        if (settings.request_timeout < 5 || settings.request_timeout > 300) {
            Toast.warning('请求超时必须在5-300秒之间');
            return false;
        }

        if (settings.api_rate_limit < 1 || settings.api_rate_limit > 200) {
            Toast.warning('API速率限制必须在1-200之间');
            return false;
        }

        if (settings.rate_limit_window < 0.1 || settings.rate_limit_window > 10) {
            Toast.warning('速率窗口必须在0.1-10秒之间');
            return false;
        }

        return true;
    }

    // 更新UI
    updateUI() {
        document.getElementById('setting_max_workers').value = this.currentSettings.max_workers;
        document.getElementById('setting_request_rate_limit').value = this.currentSettings.request_rate_limit;
        document.getElementById('setting_connection_pool_size').value = this.currentSettings.connection_pool_size;
        document.getElementById('setting_async_batch_size').value = this.currentSettings.async_batch_size;
        document.getElementById('setting_max_retries').value = this.currentSettings.max_retries;
        document.getElementById('setting_request_timeout').value = this.currentSettings.request_timeout;
        document.getElementById('setting_api_rate_limit').value = this.currentSettings.api_rate_limit;
        document.getElementById('setting_rate_limit_window').value = this.currentSettings.rate_limit_window;
    }

    // 显示消息
    showMessage(type, message) {
        const messageEl = document.getElementById('settingsMessage');
        if (!messageEl) return;

        messageEl.className = `settings-message ${type}`;
        messageEl.textContent = message;
        messageEl.style.display = 'block';

        setTimeout(() => {
            messageEl.style.display = 'none';
        }, 3000);
    }
}

// 初始化设置管理器
const settingsManager = new SettingsManager();

// 在DOMContentLoaded事件中初始化设置页面
document.addEventListener('DOMContentLoaded', () => {
    // 延迟初始化,等待国际化加载完成
    setTimeout(() => {
        settingsManager.init();
    }, 500);
});
