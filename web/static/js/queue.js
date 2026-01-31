/* ===================== 队列管理器 ===================== */

import Toast from './toast.js';

class QueueManager {
    constructor() {
        this.storageKey = 'fanqie_download_queue_v2';
        this.statusPollInterval = null;
        this.serverTasks = [];
        this.visibilityHandler = null;
        this.lastBatchStatus = null;
    }
    
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
    
    getLocalQueue() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            console.error('读取队列失败:', e);
            return [];
        }
    }
    
    saveLocalQueue(queue) {
        localStorage.setItem(this.storageKey, JSON.stringify(queue));
    }
    
    add(task) {
        const queue = this.getLocalQueue();
        const exists = queue.some(t => t.book_id === task.book_id);
        if (!exists) {
            queue.push({ ...task, status: 'pending', id: Date.now() + Math.random() });
            this.saveLocalQueue(queue);
            this.render();
            Toast.success(`已添加到队列: ${task.book_name}`);
        } else {
            Toast.warning('该书籍已在队列中');
        }
    }
    
    remove(id) {
        let queue = this.getLocalQueue();
        queue = queue.filter(t => t.id !== id);
        this.saveLocalQueue(queue);
        this.render();
    }
    
    clear() {
        this.saveLocalQueue([]);
        this.render();
        Toast.info('队列已清空');
    }

    updateSummary(totalCount) {
        const summary = document.getElementById('queueSummary');
        if (summary) summary.textContent = String(totalCount);
    }

    updateControls() {
        const controls = document.getElementById('queueControls');
        if (!controls) return;

        const isDownloading = !!this.lastBatchStatus?.is_downloading;
        controls.style.display = isDownloading ? 'flex' : 'none';

        const retryBtn = document.getElementById('retryAllBtn');
        if (retryBtn) {
            const failedCount = (this.lastBatchStatus?.results || []).filter(r => r && r.success === false).length;
            retryBtn.style.display = failedCount > 0 ? 'inline-flex' : 'none';
        }
    }
    
    async render() {
        const container = document.getElementById('queueList');
        if (!container) return;
        
        const queue = this.getLocalQueue();
        const serverStatus = await this.fetchServerStatus();

        const totalCount = queue.length + serverStatus.length;
        this.updateSummary(totalCount);
        this.updateControls();
        
        if (queue.length === 0 && serverStatus.length === 0) {
            container.innerHTML = `
                <div class="queue-empty">
                    <svg class="queue-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                    </svg>
                    <div class="queue-empty-text">队列为空，添加书籍开始下载</div>
                </div>
            `;
            return;
        }
        
        const allTasks = [...queue, ...serverStatus];
        
        container.innerHTML = allTasks.map(task => `
            <div class="queue-item" data-id="${task.id}">
                <div class="queue-status-icon">
                    ${this.getStatusIcon(task.status)}
                </div>
                <div class="queue-info">
                    <div class="queue-name">${task.book_name || task.book_id}</div>
                    <div class="queue-meta">
                        ${task.status === 'downloading' ? `进度: ${task.progress || 0}%` : 
                          task.status === 'completed' ? '下载完成' : 
                          task.status === 'failed' ? `失败: ${task.message || '未知错误'}` : 
                          task.status === 'skipped' ? '已跳过' : '等待中'}
                    </div>
                </div>
                <div class="queue-actions">
                    ${task.status === 'pending' ? `
                        <button class="icon-btn icon-btn-sm" onclick="QueueManager.remove(${task.id})" title="移除">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }
    
    async fetchServerStatus() {
        try {
            const res = await fetch(`/api/batch-status?t=${Date.now()}`);
            const data = await res.json();
            this.lastBatchStatus = data;
            if (data.is_downloading) {
                return [{
                    id: 'server',
                    book_id: data.current_book || '处理中',
                    book_name: data.current_book || '处理中',
                    status: 'downloading',
                    progress: 0,
                    message: data.message || ''
                }];
            }
        } catch (e) {
            console.error('获取服务器状态失败:', e);
        }
        this.lastBatchStatus = null;
        return [];
    }
    
    startStatusPolling() {
        if (this.statusPollInterval) return;
        this.statusPollInterval = setInterval(() => this.render(), 2000);
        
        this.visibilityHandler = () => {
            if (!document.hidden) this.render();
        };
        document.addEventListener('visibilitychange', this.visibilityHandler);
    }
    
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
}

const queueManager = new QueueManager();

export default queueManager;
