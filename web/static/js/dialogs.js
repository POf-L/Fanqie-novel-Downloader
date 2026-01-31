/* ===================== 确认对话框组件 ===================== */

import api from './api.js';
import Toast from './toast.js';

class ConfirmDialog {
    static show(message, onConfirm, options = {}) {
        const {
            title = '确认操作',
            confirmText = '确认',
            cancelText = '取消',
            confirmClass = 'btn-primary'
        } = options;
        
        const overlay = document.createElement('div');
        overlay.className = 'modal';
        overlay.innerHTML = `
            <div class="modal-content modal-sm">
                <div class="modal-header">
                    <h3 class="modal-title">${title}</h3>
                    <button class="modal-close" onclick="ConfirmDialog.close()">×</button>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="ConfirmDialog.close()">${cancelText}</button>
                    <button class="btn ${confirmClass}" id="confirmBtn">${confirmText}</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        overlay.style.display = 'flex';
        
        overlay.querySelector('#confirmBtn').addEventListener('click', () => {
            this.close();
            onConfirm();
        });
        
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.close();
        });
        
        this.currentOverlay = overlay;
    }
    
    static close() {
        if (this.currentOverlay) {
            this.currentOverlay.remove();
            this.currentOverlay = null;
        }
    }
}

/* ===================== 重复下载确认对话框 ===================== */

class DuplicateDialog {
    static show(task, onConfirm) {
        const overlay = document.createElement('div');
        overlay.className = 'modal';
        overlay.innerHTML = `
            <div class="modal-content modal-sm">
                <div class="modal-header">
                    <h3 class="modal-title">重复下载</h3>
                    <button class="modal-close" onclick="DuplicateDialog.close()">×</button>
                </div>
                <div class="modal-body">
                    <p><strong>${task.book_name}</strong> 已经下载过，是否重新下载？</p>
                    <p style="margin-top: 12px; color: var(--text-muted); font-size: 13px;">
                        上次下载时间: ${task.last_download_time || '未知'}
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="DuplicateDialog.close()">取消</button>
                    <button class="btn btn-primary" id="redownloadBtn">重新下载</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        overlay.style.display = 'flex';
        
        overlay.querySelector('#redownloadBtn').addEventListener('click', () => {
            this.close();
            onConfirm();
        });
        
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.close();
        });
        
        this.currentOverlay = overlay;
    }
    
    static close() {
        if (this.currentOverlay) {
            this.currentOverlay.remove();
            this.currentOverlay = null;
        }
    }
}

/* ===================== 文件夹浏览器组件 ===================== */

class FolderBrowser {
    static async show(onSelect) {
        const overlay = document.createElement('div');
        overlay.className = 'modal';
        overlay.innerHTML = `
            <div class="modal-content folder-browser-dialog">
                <div class="modal-header">
                    <h3 class="modal-title">选择文件夹</h3>
                    <button class="modal-close" id="folderBrowserCloseBtn">×</button>
                </div>
                <div class="modal-body">
                    <div id="folderBrowserContent"></div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" id="folderBrowserCancelBtn">取消</button>
                    <button class="btn btn-primary" id="selectFolderBtn" disabled>选择当前文件夹</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        overlay.style.display = 'flex';
        
        this.currentOverlay = overlay;
        this.onSelect = onSelect;
        this.currentPath = '';
        this.selectedPath = '';
        
        overlay.querySelector('#folderBrowserCloseBtn').addEventListener('click', () => this.close());
        overlay.querySelector('#folderBrowserCancelBtn').addEventListener('click', () => this.close());
        
        await this.loadDirectory('');
        
        overlay.querySelector('#selectFolderBtn').addEventListener('click', () => {
            if (this.selectedPath) {
                this.close();
                this.onSelect(this.selectedPath);
            }
        });
        
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.close();
        });
    }
    
    static async loadDirectory(path) {
        try {
            const data = await api.request('/api/list-directory', {
                method: 'POST',
                body: JSON.stringify({ path })
            });
            
            if (data.success) {
                this.currentPath = data.data.current_path;
                this.selectedPath = data.data.current_path;
                this.render(data.data);
            } else {
                this.renderError(data.message || '加载目录失败');
            }
        } catch (e) {
            console.error('加载目录失败:', e);
            this.renderError('加载目录失败');
        }
    }

    static renderError(message) {
        const content = this.currentOverlay?.querySelector('#folderBrowserContent');
        if (!content) return;
        content.innerHTML = `
            <div class="folder-error">
                <span>${message}</span>
            </div>
        `;
        const selectBtn = this.currentOverlay.querySelector('#selectFolderBtn');
        if (selectBtn) selectBtn.disabled = true;
        Toast.error(message);
    }
    
    static render(data) {
        const content = this.currentOverlay.querySelector('#folderBrowserContent');
        
        let html = '';
        
        html += '<div class="folder-browser-path"><input type="text" class="form-input path-input" value="' + (data.current_path || '').replace(/"/g, '&quot;') + '" readonly></div>';
        
        html += '<div class="folder-browser-toolbar">';
        
        if (data.drives && data.drives.length > 0) {
            html += '<div class="folder-browser-drives">';
            data.drives.forEach(drive => {
                const escapedPath = drive.path.replace(/"/g, '&quot;');
                html += `<button class="btn btn-sm btn-secondary drive-btn folder-nav-item" data-path="${escapedPath}">${drive.name}</button>`;
            });
            html += '</div>';
        }
        
        if (data.quick_paths && data.quick_paths.length > 0) {
            html += '<div class="folder-browser-quick">';
            data.quick_paths.forEach(qp => {
                const escapedPath = qp.path.replace(/"/g, '&quot;');
                html += `<button class="btn btn-sm btn-secondary quick-btn folder-nav-item" data-path="${escapedPath}" title="${qp.name}"><iconify-icon icon="${qp.icon}"></iconify-icon></button>`;
            });
            html += '</div>';
        }
        
        html += '</div>';
        
        html += '<div class="folder-browser-list">';
        
        if (data.parent_path) {
            const escapedParentPath = data.parent_path.replace(/"/g, '&quot;');
            html += `
                <div class="folder-item folder-nav-item" data-path="${escapedParentPath}">
                    <iconify-icon icon="line-md:arrow-left" style="font-size:20px;color:var(--primary);"></iconify-icon>
                    <span>..</span>
                </div>
            `;
        }
        
        data.directories.forEach(dir => {
            const isSelected = dir.path === this.selectedPath;
            const escapedPath = dir.path.replace(/"/g, '&quot;');
            html += `
                <div class="folder-item folder-nav-item ${isSelected ? 'selected' : ''}" data-path="${escapedPath}">
                    <iconify-icon icon="line-md:folder" style="font-size:20px;color:var(--primary);"></iconify-icon>
                    <span>${dir.name}</span>
                </div>
            `;
        });
        
        if (data.directories.length === 0 && !data.parent_path) {
            html += '<div class="folder-empty"><iconify-icon icon="line-md:folder-off"></iconify-icon><span>空目录</span></div>';
        }
        
        html += '</div>';
        content.innerHTML = html;
        
        content.querySelectorAll('.folder-nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const path = item.dataset.path;
                if (path) FolderBrowser.loadDirectory(path);
            });
        });
        
        this.currentOverlay.querySelector('#selectFolderBtn').disabled = false;
    }
    
    static close() {
        if (this.currentOverlay) {
            this.currentOverlay.remove();
            this.currentOverlay = null;
        }
    }
}

export { ConfirmDialog, DuplicateDialog, FolderBrowser };
