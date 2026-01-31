/* ===================== 下载接口选择 ===================== */

import api from './api.js';
import Toast from './toast.js';

class ApiSelector {
    static async loadAndShow() {
        const result = await api.getApiSources();
        if (!result.success) {
            Toast.error('获取接口列表失败');
            return;
        }
        
        this.show(result.sources, result.current, result.mode);
    }
    
    static show(sources, current, mode) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        const sortedSources = [...sources].sort((a, b) => {
            if (a.available === b.available) return 0;
            return a.available ? -1 : 1;
        });
        
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <h3 class="modal-title">选择下载接口</h3>
                    <button class="modal-close" onclick="ApiSelector.close()">×</button>
                </div>
                <div class="modal-body">
                    <div class="tabs" style="margin-bottom: 16px;">
                        <button class="tab ${mode === 'auto' ? 'active' : ''}" onclick="ApiSelector.setMode('auto', this)">自动选择</button>
                        <button class="tab ${mode === 'manual' ? 'active' : ''}" onclick="ApiSelector.setMode('manual', this)">手动选择</button>
                    </div>
                    <div id="apiSourceList" style="max-height: 300px; overflow-y: auto;">
                        ${sortedSources.map((source, index) => `
                            <div class="sidebar-item ${source.base_url === current ? 'active' : ''}" 
                                 onclick="ApiSelector.select('${source.base_url}')">
                                <span style="flex: 1;">
                                    <strong>${source.dynamic_name || source.name || source.base_url}</strong>
                                </span>
                                <span class="badge ${source.available ? 'badge-success' : 'badge-danger'}">
                                    ${source.available ? '可用' : '不可用'}
                                </span>
                                ${source.latency_ms ? `<small style="color: var(--text-muted);">${source.latency_ms}ms</small>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="ApiSelector.close()">取消</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        this.currentMode = mode;
        this.overlay = overlay;
    }
    
    static setMode(mode, btn) {
        this.currentMode = mode;
        btn.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        
        if (mode === 'auto') {
            this.selectAuto();
        }
    }
    
    static async setModeAndSave(mode) {
        const result = await api.selectApiSource(mode);
        if (result.success) {
            Toast.success(`已切换到${mode === 'auto' ? '自动' : '手动'}模式`);
            this.close();
        } else {
            Toast.error(result.message || '切换失败');
        }
    }
    
    static async selectAuto() {
        const result = await api.selectApiSource('auto');
        if (result.success) {
            Toast.success(`已自动选择最优接口`);
            this.close();
        } else {
            Toast.error(result.message || '自动选择失败');
        }
    }
    
    static async select(baseUrl) {
        const result = await api.selectApiSource('manual', baseUrl);
        if (result.success) {
            Toast.success(`已选择: ${baseUrl}`);
            this.close();
        } else {
            Toast.error(result.message || '选择失败');
        }
    }
    
    static close() {
        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }
    }
}

export default ApiSelector;
