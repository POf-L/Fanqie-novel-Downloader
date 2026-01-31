/* ===================== 全局状态管理 ===================== */

class AppState {
    static _memoryStore = new Map();

    static _key(key) {
        return `fanqie_${key}`;
    }

    static get(key) {
        const storageKey = this._key(key);
        try {
            const value = localStorage.getItem(storageKey);
            if (value !== null) return value;
        } catch (e) {
            // ignore
        }

        return this._memoryStore.has(storageKey) ? this._memoryStore.get(storageKey) : null;
    }
    
    static set(key, value) {
        const storageKey = this._key(key);
        // 始终写入内存，避免某些 WebView 禁用 localStorage 导致启动卡住
        try {
            this._memoryStore.set(storageKey, String(value ?? ''));
        } catch (e) {
            // ignore
        }
        try {
            localStorage.setItem(storageKey, String(value ?? ''));
            return true;
        } catch (e) {
            console.error('保存状态失败:', e);
            return false;
        }
    }
    
    static remove(key) {
        const storageKey = this._key(key);
        try {
            this._memoryStore.delete(storageKey);
        } catch (e) {
            // ignore
        }
        try {
            localStorage.removeItem(storageKey);
            return true;
        } catch (e) {
            return false;
        }
    }
    
    static getAccessToken() {
        return this.get('access_token');
    }
    
    static setAccessToken(token) {
        this.set('access_token', token);
    }
    
    static getSavePath() {
        return this.get('save_path') || '';
    }
    
    static setSavePath(path) {
        this.set('save_path', path);
    }
    
    static getApiUrl() {
        return this.get('api_url') || '';
    }
    
    static setApiUrl(url) {
        this.set('api_url', url);
    }
    
    static getSelectedChapters() {
        try {
            return JSON.parse(this.get('selected_chapters') || '[]');
        } catch {
            return [];
        }
    }
    
    static setSelectedChapters(chapters) {
        this.set('selected_chapters', JSON.stringify(chapters));
    }
    
    static clearSelectedChapters() {
        this.remove('selected_chapters');
    }
}

export default AppState;
