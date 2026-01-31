/* ===================== UI 事件处理 ===================== */

import AppState from './state.js';
import api from './api.js';
import ApiSelector from './api_selector.js';
import QueueManager from './queue.js';
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
    QueueManager.startStatusPolling();

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
            const result = await api.request('/api/queue/retry', {
                method: 'POST',
                body: JSON.stringify({ retry_all: true })
            });
            if (result.success) {
                Toast.success(result.message || '已重试失败任务');
            } else {
                Toast.error(result.message || '没有失败任务');
            }
        });
    }

    const forceSaveBtn = document.getElementById('forceSaveBtn');
    if (forceSaveBtn) {
        forceSaveBtn.addEventListener('click', () => {
            Toast.info('强制保存暂未支持');
        });
    }

    const copyLogBtn = document.getElementById('copyLogBtn');
    if (copyLogBtn) {
        copyLogBtn.addEventListener('click', async () => {
            const content = Logger.getText();
            if (!content) {
                Toast.info('暂无日志可复制');
                return;
            }
            try {
                await navigator.clipboard.writeText(content);
                Toast.success('日志已复制');
            } catch {
                Toast.error('复制失败，请手动复制');
            }
        });
    }

    const clearLogBtn = document.getElementById('clearLogBtn');
    if (clearLogBtn) {
        clearLogBtn.addEventListener('click', () => {
            Logger.clear();
            Toast.info('日志已清空');
        });
    }

    initSettingsUI();

    fetchVersion();
    initChapterModalEvents();
    initSearchListInteractions();

    initWindowControls();
    initPathAutoResize();
    initVersionCheck();
}

function initTabSystem() {
    document.querySelectorAll('.tab-nav').forEach(nav => {
        nav.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetId = btn.dataset.tab;
                if (!targetId) return;
                nav.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
                btn.classList.add('active');
                const container = nav.closest('.card, .main-content, .dashboard-main');
                if (container) {
                    container.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
                    const targetPane = container.querySelector(`#tab-${targetId}`);
                    if (targetPane) targetPane.classList.add('active');
                }
            });
        });
    });
}

async function loadApiSources() {
    const select = document.getElementById('apiSourceSelect');
    const statusEl = document.getElementById('apiNodeStatus');
    if (!select) return;

    select.disabled = true;
    select.innerHTML = '<option value="">测速中...</option>';
    if (statusEl) {
        statusEl.innerHTML = '<iconify-icon icon="line-md:loading-twotone-loop" class="spin"></iconify-icon>';
    }

    try {
        const result = await api.getApiSources();
        if (result.success && Array.isArray(result.sources)) {
            select.innerHTML = '';
            const sorted = [...result.sources].sort((a, b) => {
                if (a.available === b.available) {
                    return (a.latency_ms || 99999) - (b.latency_ms || 99999);
                }
                return a.available ? -1 : 1;
            });
            sorted.forEach(src => {
                const opt = document.createElement('option');
                opt.value = src.base_url;
                const status = src.available ? '' : ' (不可用)';
                const latency = src.latency_ms ? ` ${src.latency_ms}ms` : '';
                const displayName = src.dynamic_name || src.name || src.base_url;
                opt.textContent = `${displayName}${latency}${status}`;
                opt.disabled = !src.available;
                if (src.base_url === result.current) opt.selected = true;
                select.appendChild(opt);
            });
            const availableCount = sorted.filter(s => s.available).length;
            if (statusEl) {
                statusEl.innerHTML = `<span class="badge badge-success">${availableCount} 可用</span>`;
            }
        } else {
            select.innerHTML = '<option value="">无可用节点</option>';
            if (statusEl) {
                statusEl.innerHTML = '<span class="badge badge-danger">无节点</span>';
            }
        }
    } catch (e) {
        select.innerHTML = '<option value="">加载失败</option>';
        if (statusEl) {
            statusEl.innerHTML = '<span class="badge badge-danger">错误</span>';
        }
    } finally {
        select.disabled = false;
    }
}

async function initApiSourceControls() {
    const select = document.getElementById('apiSourceSelect');
    if (!select) return;

    select.addEventListener('change', async () => {
        const baseUrl = select.value;
        if (baseUrl) {
            const result = await api.selectApiSource('manual', baseUrl);
            if (result.success) {
                Toast.success('节点已切换');
            } else {
                Toast.error(result.message || '选择失败');
            }
        }
    });

    const refreshBtn = document.getElementById('refreshApiNodesBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.disabled = true;
            await loadApiSources();
            refreshBtn.disabled = false;
            Toast.success('节点列表已刷新');
        });
    }

    await loadApiSources();
}

function initApiSourceControlsLazy() {
    const select = document.getElementById('apiSourceSelect');
    if (!select) return;

    const refreshBtn = document.getElementById('refreshApiNodesBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            refreshBtn.disabled = true;
            await loadApiSources();
            refreshBtn.disabled = false;
            Toast.success('节点列表已刷新');
        });
    }

    select.addEventListener('change', async () => {
        const baseUrl = select.value;
        if (baseUrl) {
            const result = await api.selectApiSource('manual', baseUrl);
            if (result.success) {
                Toast.success('节点已切换');
            } else {
                Toast.error(result.message || '选择失败');
            }
        }
    });

    setTimeout(() => loadApiSources(), 1000);
}

function initChapterModalEvents() {
    const modal = document.getElementById('chapterModal');
    if (!modal) return;

    const updateSelectedCount = () => {
        const count = modal.querySelectorAll('.chapter-checkbox:checked').length;
        const counter = document.getElementById('selectedCount');
        if (counter) counter.textContent = count;
    };

    document.getElementById('chapterModalClose')?.addEventListener('click', closeChapterModal);
    document.getElementById('cancelChaptersBtn')?.addEventListener('click', closeChapterModal);

    document.getElementById('selectAllBtn')?.addEventListener('click', () => {
        modal.querySelectorAll('.chapter-checkbox').forEach(cb => (cb.checked = true));
        updateSelectedCount();
    });

    document.getElementById('selectNoneBtn')?.addEventListener('click', () => {
        modal.querySelectorAll('.chapter-checkbox').forEach(cb => (cb.checked = false));
        updateSelectedCount();
    });

    document.getElementById('selectInvertBtn')?.addEventListener('click', () => {
        modal.querySelectorAll('.chapter-checkbox').forEach(cb => (cb.checked = !cb.checked));
        updateSelectedCount();
    });

    document.getElementById('confirmChaptersBtn')?.addEventListener('click', () => {
        const selected = [];
        modal.querySelectorAll('.chapter-checkbox:checked').forEach(cb => {
            selected.push(cb.dataset.id);
        });
        AppState.setSelectedChapters(selected);
        closeChapterModal();
        Toast.success(`已选择 ${selected.length} 章`);
    });

    modal.addEventListener('change', (e) => {
        if (e.target.classList.contains('chapter-checkbox')) {
            updateSelectedCount();
        }
    });
}

function initSearchListInteractions() {
    const container = document.getElementById('searchResultList');
    if (!container) return;

    container.addEventListener('click', (e) => {
        const actionBtn = e.target.closest('button[data-action]');
        if (actionBtn) {
            const action = actionBtn.dataset.action;
            const item = actionBtn.closest('.search-item');
            const bookId = item?.dataset.bookId;
            const bookName = item?.dataset.bookName;
            if (action === 'download') {
                handleDownload(bookId, bookName);
            } else if (action === 'queue') {
                handleAddToQueue(bookId, bookName);
            } else if (action === 'toggle-desc') {
                const desc = item?.querySelector('.search-desc');
                if (desc) desc.classList.toggle('collapsed');
            }
            return;
        }

        const toggleBtn = e.target.closest('.desc-toggle');
        if (toggleBtn) {
            const item = toggleBtn.closest('.search-item');
            const desc = item?.querySelector('.search-desc');
            if (desc) desc.classList.toggle('collapsed');
        }
    });
}

function initWindowControls() {
    const minBtn = document.getElementById('winMinimize');
    const maxBtn = document.getElementById('winMaximize');
    const closeBtn = document.getElementById('winClose');

    if (!minBtn || !maxBtn || !closeBtn) return;
    if (minBtn.dataset.bound === 'true') return;
    minBtn.dataset.bound = 'true';
    maxBtn.dataset.bound = 'true';
    closeBtn.dataset.bound = 'true';

    const isPyWebView = () => window.pywebview && window.pywebview.api;

    minBtn.addEventListener('click', () => {
        if (isPyWebView()) window.pywebview.api.minimize_window();
    });

    maxBtn.addEventListener('click', () => {
        if (isPyWebView()) window.pywebview.api.toggle_maximize();
    });

    closeBtn.addEventListener('click', () => {
        if (isPyWebView()) window.pywebview.api.close_window();
        else window.close();
    });

    initWindowDrag();
}

function initWindowDrag() {
    const header = document.querySelector('.dashboard-header');
    if (!header) return;

    const isPyWebView = () => window.pywebview && window.pywebview.api;

    header.addEventListener('mousedown', (e) => {
        if (!isPyWebView()) return;
        if (e.button !== 0) return;
        if (e.target.closest('button, input, select, textarea, a, .header-actions, .api-select-wrapper')) return;

        const offsetX = e.screenX - window.screenX;
        const offsetY = e.screenY - window.screenY;
        window.pywebview.api.start_drag(offsetX, offsetY);

        const onMouseMove = (e) => {
            if (isPyWebView()) window.pywebview.api.drag_window(e.screenX, e.screenY);
        };

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

function initVersionCheck() {
    const btn = document.getElementById('versionBtn');
    if (btn) {
        btn.addEventListener('click', async () => {
            const result = await api.checkUpdate();
            if (result.success && result.has_update) {
                Toast.info('发现新版本，请在更新弹窗中查看');
            } else {
                Toast.info('当前是最新版本');
            }
        });
    }
}

export {
    initializeUI,
    initTabSystem,
    initApiSourceControls,
    initApiSourceControlsLazy,
    loadApiSources,
    initChapterModalEvents,
    initSearchListInteractions,
    initWindowControls,
    initWindowDrag,
    initVersionCheck
};
