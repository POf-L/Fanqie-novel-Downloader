/* ===================== 版本管理 ===================== */

const VersionManager = {
    currentVersion: '1.1.0',
    
    async checkForUpdates() {
        try {
            const res = await fetch(`/api/check-update?t=${Date.now()}`);
            return await res.json();
        } catch (e) {
            console.error('检查更新失败:', e);
            return { success: false, has_update: false };
        }
    },
    
    async downloadUpdate(url, filename) {
        try {
            const res = await fetch('/api/download-update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, filename })
            });
            return await res.json();
        } catch (e) {
            console.error('下载更新失败:', e);
            return { success: false, message: e.message };
        }
    },
    
    async applyUpdate() {
        try {
            const res = await fetch('/api/apply-update', { method: 'POST' });
            return await res.json();
        } catch (e) {
            console.error('应用更新失败:', e);
            return { success: false, message: e.message };
        }
    }
};

export default VersionManager;
