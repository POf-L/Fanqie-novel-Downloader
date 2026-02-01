/* ===================== 统一任务管理器 ===================== */

import Toast from './toast.js';
import Logger from './logger.js';
import api from './api.js';

class UnifiedTaskManager {
    constructor() {
        this.storageKey = 'fanqie_unified_tasks_v3';
        this.statusPollInterval = null;
        this.serverTasks = [];
        this.localQueue = [];
        this.visibilityHandler = null;
        this.currentBook = null;
        this.downloadStats = {
            pending: 0,
            downloading: 0,
            completed: 0,
            failed: 0
        };
        this.isDownloading = false;
        this.downloadSpeed = 0;
        this.elapsedTime = 0;
        this.currentProgress = 0;
        this.currentMessage = '';
    }

    getTasks() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            console.error('读取任务失败:', e);
            return [];
        }
    }

    saveTasks(tasks) {
        localStorage.setItem(this.storageKey, JSON.stringify(tasks));
    }

    add(task) {
        const tasks = this.getTasks();
        const exists = tasks.some(t => t.book_id === task.book_id && t.status === 'pending');
        if (!exists) {
            const newTask = {
                ...task,
                status: 'pending',
                id: Date.now() + Math.random(),
                added_at: new Date().toISOString()
            };
            tasks.push(newTask);
            this.saveTasks(tasks);
            this.render();
            this.updateStats();
            Toast.success(`已添加到任务: ${task.book_name}`);
        } else {
            Toast.warning('该书籍已在待下载队列中');
        }
    }

    remove(id) {
        let tasks = this.getTasks();
        tasks = tasks.filter(t => t.id !== id);
        this.saveTasks(tasks);
        this.render();
        this.updateStats();
    }

    clear() {
        this.saveTasks([]);
        this.render();
        this.updateStats();
        Toast.info('任务队列已清空');
    }

    getStatusIcon(status) {
        const icons = {
            pending: '<iconify-icon icon="line-md:circle"></iconify-icon>',
            downloading: '<iconify-icon icon="line-md:loading-twotone-loop" class="spin"></iconify-icon>',
            completed: '<iconify-icon icon="line-md:confirm-circle"></iconify-icon>',
            failed: '<iconify-icon icon="icon-park-outline:error"></iconify-icon>',
            skipped: '<iconify-icon icon="line-md:arrow-right-circle"></iconify-icon>'
        };
        return icons[status] || icons.pending;
    }

    getStatusText(status) {
        const texts = {
            pending: '等待中',
            downloading: '下载中',
            completed: '已完成',
            failed: '失败',
            skipped: '已跳过'
        };
        return texts[status] || '未知';
    }

    async fetchServerStatus() {
        try {
            const res = await fetch(`/api/batch-status?t=${Date.now()}`);
            const data = await res.json();
            
            this.isDownloading = data.is_downloading;
            this.currentBook = data.current_book || null;
            this.downloadSpeed = data.download_speed || 0;
            this.elapsedTime = data.elapsed_time || 0;
            this.currentProgress = data.progress || 0;
            this.currentMessage = data.message || '';

            if (data.is_downloading && data.current_book) {
                return {
                    id: 'current',
                    book_id: data.current_book_id || 'current',
                    book_name: data.current_book,
                    status: 'downloading',
                    progress: data.progress || 0,
                    message: data.message || '下载中...'
                };
            }

            const results = data.results || [];
            results.forEach(result => {
                if (result.book_id) {
                    this.updateTaskStatus(result.book_id, result.success ? 'completed' : 'failed', result.message);
                }
            });

            return [];
        } catch (e) {
            console.error('获取服务器状态失败:', e);
        }
        return [];
    }

    updateTaskStatus(bookId, status, message = '') {
        const tasks = this.getTasks();
        let updated = false;

        tasks.forEach(task => {
            if (task.book_id === bookId && task.status === 'pending') {
                task.status = status;
                task.message = message;
                if (status === 'completed') {
                    task.completed_at = new Date().toISOString();
                }
                updated = true;
            }
        });

        if (updated) {
            this.saveTasks(tasks);
            this.updateStats();
        }
    }

    calculateStats() {
        const tasks = this.getTasks();
        const stats = {
            pending: 0,
            downloading: 0,
            completed: 0,
            failed: 0
        };

        tasks.forEach(task => {
            if (task.status && stats[task.status] !== undefined) {
                stats[task.status]++;
            }
        });

        if (this.isDownloading) {
            stats.downloading++;
        }

        return stats;
    }

    updateStats() {
        const stats = this.calculateStats();
        this.downloadStats = stats;

        document.getElementById('statPending').textContent = stats.pending;
        document.getElementById('statDownloading').textContent = stats.downloading;
        document.getElementById('statCompleted').textContent = stats.completed;
        document.getElementById('statFailed').textContent = stats.failed;

        document.getElementById('bookNameMain').textContent = this.currentBook || '-';
        document.getElementById('downloadSpeed').textContent = this.downloadSpeed > 0 ? `${this.downloadSpeed} KB/s` : '0 KB/s';
        document.getElementById('elapsedTime').textContent = this.elapsedTime > 0 ? `${this.elapsedTime}s` : '0s';
        document.getElementById('progressPercentMain').textContent = `${this.currentProgress}%`;
        document.getElementById('progressFillMain').style.width = `${this.currentProgress}%`;

        const statusBadge = document.getElementById('statusTextMain');
        if (statusBadge) {
            if (this.isDownloading) {
                statusBadge.innerHTML = '<iconify-icon icon="line-md:downloading-loop" class="spin"></iconify-icon>';
            } else {
                statusBadge.innerHTML = '<iconify-icon icon="line-md:confirm-circle"></iconify-icon>';
            }
        }
    }

    updateControls() {
        const controls = document.getElementById('queueControls');
        if (!controls) return;

        controls.style.display = this.isDownloading ? 'flex' : 'none';

        const retryBtn = document.getElementById('retryAllBtn');
        if (retryBtn) {
            const failedCount = this.downloadStats.failed;
            retryBtn.style.display = failedCount > 0 ? 'inline-flex' : 'none';
        }
    }

    async render() {
        const container = document.getElementById('queueList');
        if (!container) return;

        const localTasks = this.getTasks();
        const serverStatus = await this.fetchServerStatus();

        const allTasks = [...serverStatus, ...localTasks];
        const totalCount = allTasks.length;

        if (totalCount === 0) {
            container.innerHTML = `
                <div class="queue-empty">
                    <iconify-icon icon="line-md:coffee-half-empty-twotone-loop" class="queue-empty-icon"></iconify-icon>
                    <div class="queue-empty-text">任务队列为空</div>
                </div>
            `;
            this.updateControls();
            return;
        }

        container.innerHTML = allTasks.map(task => `
            <div class="queue-item" data-id="${task.id}">
                <div class="queue-status-icon">
                    ${this.getStatusIcon(task.status)}
                </div>
                <div class="queue-info">
                    <div class="queue-name">${task.book_name || task.book_id}</div>
                    <div class="queue-meta">
                        ${this.getStatusText(task.status)}
                        ${task.status === 'downloading' && task.progress ? ` • ${task.progress}%` : ''}
                        ${task.status === 'failed' && task.message ? ` • ${task.message}` : ''}
                    </div>
                    ${task.status === 'downloading' && task.progress ? `
                        <div class="queue-item-progress">
                            <div class="progress-bar-mini">
                                <div class="progress-fill" style="width: ${task.progress}%"></div>
                            </div>
                        </div>
                    ` : ''}
                </div>
                <div class="queue-actions">
                    ${task.status === 'pending' ? `
                        <button class="icon-btn icon-btn-sm" onclick="TaskManager.remove(${task.id})" title="移除">
                            <iconify-icon icon="line-md:close"></iconify-icon>
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');

        this.updateStats();
        this.updateControls();
    }

    startStatusPolling() {
        if (this.statusPollInterval) return;
        this.statusPollInterval = setInterval(() => this.render(), 1500);

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

const taskManager = new UnifiedTaskManager();

window.TaskManager = taskManager;

export default taskManager;
