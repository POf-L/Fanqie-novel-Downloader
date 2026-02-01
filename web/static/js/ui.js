/* ===================== UI 事件处理 ===================== */

import AppState from './state.js';
import api from './api.js';
import ApiSelector from './api_selector.js';
import TaskManager from './unified_task.js';
import Toast from './toast.js';
import Logger from './logger.js';
import { adjustPathFontSize, initPathAutoResize } from './path.js';
import { closeChapterModal } from './app_modals.js';
import {
    fetchVersion,
    handleAddToQueue,
    handleBrowse,
    handleCancel,
    handleClear,
    handleClearQueue,
    handleDownload,
    handleLoadFromFile,
    handleSearch,
    handleStartQueueDownload,
    initQueueListInteractions,
    renderQueue,
    clearSearchResults,
    handleLoadMoreSearchResults
} from './app_handlers.js';
import { initSettingsUI } from './settings.js';

function initializeUI(skipApiSources = false) {
    initTabSystem();

    renderQueue();
    initQueueListInteractions();
    TaskManager.startStatusPolling();

    if (!skipApiSources) {
        initApiSourceControls();
    } else {
        initApiSourceControlsLazy();
    }

    api.getSavePath().then((result) => {
        const path = result?.path || '';
        if (path) {
            AppState.setSavePath(path);
            const pathInput = document.getElementById('savePath');
            if (pathInput) {
                pathInput.value = path;
                adjustPathFontSize(pathInput);
            }
        }
    });

    document.getElementById('downloadBtn')?.addEventListener('click', () => handleAddToQueue());
    document.getElementById('cancelBtn')?.addEventListener('click', handleCancel);
    document.getElementById('clearBtn')?.addEventListener('click', handleClear);
    document.getElementById('browseBtn')?.addEventListener('click', handleBrowse);

    document.getElementById('savePath')?.addEventListener('click', handleBrowse);

    const startQueueBtn = document.getElementById('startQueueBtn');
    if (startQueueBtn) startQueueBtn.addEventListener('click', handleStartQueueDownload);
    const clearQueueBtn = document.getElementById('clearQueueBtn');
    if (clearQueueBtn) clearQueueBtn.addEventListener('click', handleClearQueue);

    const loadFromFileBtn = document.getElementById('loadFromFileBtn');
    const bookListFileInput = document.getElementById('bookListFileInput');
    if (loadFromFileBtn && bookListFileInput) {
        loadFromFileBtn.addEventListener('click', () => bookListFileInput.click());
        bookListFileInput.addEventListener('change', handleLoadFromFile);
    }

    const searchBtn = document.getElementById('searchBtn');
    if (searchBtn) searchBtn.addEventListener('click', handleSearch);
    const searchInput = document.getElementById('searchKeyword');
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSearch();
            }
        });
    }
    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
        statusFilter.addEventListener('change', handleSearch);
    }
    document.getElementById('clearSearchBtn')?.addEventListener('click', clearSearchResults);
    document.getElementById('loadMoreBtn')?.addEventListener('click', handleLoadMoreSearchResults);

    const skipCurrentBtn = document.getElementById('skipCurrentBtn');
    if (skipCurrentBtn) {
        skipCurrentBtn.addEventListener('click', async () => {
            const result = await api.request('/api/queue/skip', { method: 'POST' });
            if (result.success) {
                Toast.success(result.message || '已跳过当前任务');
            } else {
                Toast.error(result.message || '无法跳过当前任务');
            }
        });
    }

    const retryAllBtn = document.getElementById('retryAllBtn');
    if (retryAllBtn) {
        retryAllBtn.addEventListener('click', async () => {
            const result = await api.request('/api/queue/retry-failed', { method: 'POST' });
            if (result.success) {
                Toast.success(result.message || '已重试失败任务');
                TaskManager.render();
            } else {
                Toast.error(result.message || '重试失败');
            }
        });
    }

    const forceSaveBtn = document.getElementById('forceSaveBtn');
    if (forceSaveBtn) {
        forceSaveBtn.addEventListener('click', async () => {
            const result = await api.request('/api/queue/force-save', { method: 'POST' });
            if (result.success) {
                Toast.success(result.message || '已强制保存');
            } else {
                Toast.error(result.message || '强制保存失败');
            }
        });
    }

    const copyLogBtn = document.getElementById('copyLogBtn');
    if (copyLogBtn) {
        copyLogBtn.addEventListener('click', () => {
            const logContent = document.getElementById('logContentMain');
            if (logContent) {
                const text = logContent.innerText;
                navigator.clipboard.writeText(text).then(() => {
                    Toast.success('日志已复制');
                }).catch(() => {
                    Toast.error('复制失败');
                });
            }
        });
    }

    const clearLogBtn = document.getElementById('clearLogBtn');
    if (clearLogBtn) {
        clearLogBtn.addEventListener('click', () => {
            const logContent = document.getElementById('logContentMain');
            if (logContent) {
                logContent.innerHTML = '<div class="log-entry">日志已清空</div>';
                Toast.success('日志已清空');
            }
        });
    }

    initSettingsUI();
}

function initTabSystem() {
    const tabs = document.querySelectorAll('.tab-btn');
    const panes = document.querySelectorAll('.tab-pane');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            
            tabs.forEach(t => t.classList.remove('active'));
            panes.forEach(p => p.classList.remove('active'));
            
            tab.classList.add('active');
            const targetPane = document.getElementById(`tab-${targetTab}`);
            if (targetPane) {
                targetPane.classList.add('active');
            }
        });
    });
}

function initApiSourceControls() {
    ApiSelector.init();
}

function initApiSourceControlsLazy() {
    setTimeout(() => initApiSourceControls(), 2000);
}

function initChapterModalEvents() {
    const closeBtn = document.getElementById('chapterModalClose');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeChapterModal);
    }
}

function initSearchListInteractions() {
    const container = document.getElementById('searchResultList');
    if (!container) return;

    container.addEventListener('click', async (e) => {
        const action = e.target.closest('[data-action]');
        if (!action) return;

        const actionType = action.dataset.action;
        const item = action.closest('.search-item');
        if (!item) return;

        const bookId = item.dataset.bookId;
        const bookName = item.dataset.bookName;

        switch (actionType) {
            case 'download':
                handleDownload(bookId, bookName);
                break;
            case 'queue':
                handleAddToQueue(bookId, bookName);
                break;
            case 'toggle-desc':
                const desc = item.querySelector('.search-desc');
                if (desc) {
                    desc.classList.toggle('collapsed');
                    const icon = action.querySelector('iconify-icon');
                    if (icon) {
                        icon.icon = desc.classList.contains('collapsed') 
                            ? 'line-md:chevron-down' 
                            : 'line-md:chevron-up';
                    }
                }
                break;
        }
    });
}

function initWindowControls() {
    const minBtn = document.getElementById('winMinimize');
    const maxBtn = document.getElementById('winMaximize');
    const closeBtn = document.getElementById('winClose');

    if (minBtn) {
        minBtn.addEventListener('click', () => {
            if (window.pywebview) {
                window.pywebview.api.minimize_window();
            }
        });
    }

    if (maxBtn) {
        maxBtn.addEventListener('click', () => {
            if (window.pywebview) {
                window.pywebview.api.toggle_maximize();
            }
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            if (window.pywebview) {
                window.pywebview.api.close_window();
            }
        });
    }
}

function initVersionCheck() {
    setTimeout(fetchVersion, 5000);
}

export {
    initializeUI,
    initTabSystem,
    initApiSourceControls,
    initApiSourceControlsLazy,
    initChapterModalEvents,
    initSearchListInteractions,
    initWindowControls,
    initVersionCheck
};
