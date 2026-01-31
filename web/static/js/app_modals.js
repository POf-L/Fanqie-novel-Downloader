/* ===================== 弹窗相关（章节选择/更新） ===================== */

import Toast from './toast.js';
import AppState from './state.js';
import VersionManager from './version.js';
import api from './api.js';

// ===================== 章节选择弹窗 =====================

async function openChapterModal(bookId) {
    const result = await api.getBookInfo(bookId);
    if (!result.success) {
        Toast.error(result.message || '获取章节列表失败');
        return;
    }
    
    const modal = document.getElementById('chapterModal');
    const list = document.getElementById('chapterList');
    const title = modal?.querySelector('.modal-header span');
    if (title) title.textContent = `章节: ${result.data.book_name}`;
    list.innerHTML = result.data.chapters.map(ch => `
        <label class="chapter-item">
            <input type="checkbox" class="chapter-checkbox" data-id="${ch.id}" ${AppState.getSelectedChapters().includes(ch.id) ? 'checked' : ''}>
            <span class="chapter-title">${ch.index + 1}. ${ch.title}</span>
        </label>
    `).join('');
    
    modal.style.display = 'flex';
    updateSelectedCount();
    
    list.querySelectorAll('.chapter-checkbox').forEach(cb => {
        cb.addEventListener('change', updateSelectedCount);
    });
}

function closeChapterModal() {
    document.getElementById('chapterModal').style.display = 'none';
}

function updateSelectedCount() {
    const count = document.querySelectorAll('#chapterList .chapter-checkbox:checked').length;
    const counter = document.getElementById('selectedCount');
    if (counter) counter.textContent = count;
}

// ===================== 更新弹窗 =====================

function showUpdateModal(updateInfo) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h3 class="modal-title">发现新版本</h3>
            </div>
            <div class="modal-body">
                <p>当前版本: ${VersionManager.currentVersion}</p>
                <p>最新版本: ${updateInfo.latest_version}</p>
                <p style="margin-top: 12px;">${updateInfo.description || '有新版本可用，是否更新？'}</p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">暂不更新</button>
                <button class="btn btn-primary" id="startUpdateBtn">开始更新</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(overlay);
    
    overlay.querySelector('#startUpdateBtn').addEventListener('click', async () => {
        const btn = overlay.querySelector('#startUpdateBtn');
        btn.disabled = true;
        btn.textContent = '下载中...';
        
        const downloadResult = await api.downloadUpdate(updateInfo.download_url, updateInfo.filename);
        
        if (downloadResult.success) {
            btn.textContent = '下载完成，正在应用...';
            const applyResult = await api.applyUpdate();
            if (applyResult.success) {
                Toast.success('更新已启动，请稍候...');
            } else {
                Toast.error(applyResult.message || '应用更新失败');
                btn.disabled = false;
                btn.textContent = '开始更新';
            }
        } else {
            Toast.error(downloadResult.message || '下载更新失败');
            btn.disabled = false;
            btn.textContent = '开始更新';
        }
    });
}

export { closeChapterModal, openChapterModal, showUpdateModal };
