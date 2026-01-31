/* ===================== 待下载队列 ===================== */

import api from './api.js';
import Logger from './logger.js';

class DownloadQueue {
    constructor() {
        this.queue = [];
        this.processing = false;
    }
    
    add(task) {
        this.queue.push(task);
        this.render();
        if (!this.processing) {
            this.process();
        }
    }
    
    async process() {
        if (this.queue.length === 0) {
            this.processing = false;
            return;
        }
        
        this.processing = true;
        const task = this.queue.shift();
        
        try {
            const result = await api.download(task);
            if (result.success) {
                Logger.logKey('msg_download_start', task.book_name);
            } else {
                Logger.logKey('msg_download_failed', task.book_name);
            }
        } catch (e) {
            Logger.log(`处理任务失败: ${task.book_name} - ${e.message}`, 'error');
        }
        
        this.render();
        setTimeout(() => this.process(), 1000);
    }
    
    render() {
        const container = document.getElementById('pendingQueue');
        if (!container) return;
        
        if (this.queue.length === 0) {
            container.innerHTML = '<div class="list-empty"><span class="list-empty-text">等待队列为空</span></div>';
            return;
        }
        
        container.innerHTML = this.queue.map((task, index) => `
            <div class="pending-item">
                <span class="pending-index">${index + 1}</span>
                <span class="pending-name">${task.book_name || task.book_id}</span>
                <button class="icon-btn icon-btn-sm" onclick="DownloadQueue.remove(${index})">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        `).join('');
    }
    
    remove(index) {
        this.queue.splice(index, 1);
        this.render();
    }
    
    clear() {
        this.queue = [];
        this.render();
    }
}

const downloadQueue = new DownloadQueue();

export default downloadQueue;
