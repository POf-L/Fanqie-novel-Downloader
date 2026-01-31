/* ===================== API 客户端 ===================== */

import AppState from './state.js';
import Toast from './toast.js';

const api = {
    baseUrl: '',
    
    getToken() {
        return AppState.getAccessToken() || '';
    },
    
    getUrl(path) {
        const token = this.getToken();
        const separator = path.includes('?') ? '&' : '?';
        return token ? `${path}${separator}token=${token}` : path;
    },
    
    async request(url, options = {}) {
        const defaultOptions = {
            headers: { 'Content-Type': 'application/json' }
        };
        
        try {
            const res = await fetch(this.getUrl(url), { ...defaultOptions, ...options });
            
            if (res.status === 403) {
                Toast.error('访问被拒绝，请检查令牌');
                return { success: false, message: 'Forbidden' };
            }
            
            return await res.json();
        } catch (e) {
            console.error('API请求失败:', e);
            return { success: false, message: e.message };
        }
    },
    
    async init() {
        return this.request('/api/init', { method: 'POST' });
    },
    
    async checkUpdate() {
        return this.request('/api/check-update');
    },
    
    async downloadUpdate(url, filename) {
        return this.request('/api/download-update', {
            method: 'POST',
            body: JSON.stringify({ url, filename })
        });
    },
    
    async applyUpdate() {
        return this.request('/api/apply-update', { method: 'POST' });
    },
    
    async search(keyword, offset = 0) {
        return this.request('/api/search', {
            method: 'POST',
            body: JSON.stringify({ keyword, offset })
        });
    },
    
    async getBookInfo(bookId) {
        return this.request('/api/book-info', {
            method: 'POST',
            body: JSON.stringify({ book_id: bookId })
        });
    },
    
    async download(task) {
        return this.request('/api/download', {
            method: 'POST',
            body: JSON.stringify(task)
        });
    },
    
    async cancel() {
        return this.request('/api/cancel', { method: 'POST' });
    },
    
    async getStatus() {
        return this.request('/api/status');
    },
    
    async getBatchStatus() {
        return this.request('/api/batch-status');
    },
    
    async cancelBatch() {
        return this.request('/api/batch-cancel', { method: 'POST' });
    },
    
    async getApiSources() {
        return this.request('/api/api-sources');
    },
    
    async selectApiSource(mode, baseUrl = '') {
        return this.request('/api/api-sources/select', {
            method: 'POST',
            body: JSON.stringify({ mode, base_url: baseUrl })
        });
    },
    
    async getSavePath() {
        return this.request('/api/config/save-path');
    },
    
    async setSavePath(path) {
        return this.request('/api/config/save-path', {
            method: 'POST',
            body: JSON.stringify({ path })
        });
    },
    
    async getSettings() {
        return this.request('/api/settings/get');
    },
    
    async saveSettings(settings) {
        return this.request('/api/settings/save', {
            method: 'POST',
            body: JSON.stringify({ settings })
        });
    }
};

export default api;
