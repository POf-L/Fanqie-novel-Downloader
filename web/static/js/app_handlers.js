/* ===================== 应用功能处理（搜索/下载/队列/版本） ===================== */

import Toast from './toast.js';
import QueueManager from './queue.js';
import { ConfirmDialog } from './dialogs.js';
import Logger from './logger.js';
import api from './api.js';
import { handleSelectFolder } from './settings.js';

const searchState = {
    keyword: '',
    offset: 0,
    hasMore: false,
    loading: false
};

function normalizeBookId(input) {
    if (!input) return '';
    const text = String(input).trim();
    if (!text) return '';
    if (text.includes('fanqienovel.com')) {
        const match = text.match(/\/page\/(\d+)/);
        if (match) return match[1];
    }
    return text;
}

function getSelectedFormat() {
    const select = document.getElementById('fileFormat');
    if (select?.value) return select.value;
    const radio = document.querySelector('input[name="format"]:checked');
    if (radio?.value) return radio.value;
    return 'txt';
}

function getInputBookId() {
    const input = document.getElementById('bookId');
    return normalizeBookId(input?.value || '');
}

function getSearchResultContainer() {
    return document.getElementById('searchResultList');
}

function updateSearchHeader(total) {
    const header = document.getElementById('searchHeader');
    const countEl = document.getElementById('searchResultCount');
    if (countEl) countEl.textContent = String(total);
    if (header) header.style.display = total > 0 ? 'flex' : 'none';
}

function toggleLoadMore(show) {
    const loadMoreContainer = document.getElementById('loadMoreContainer');
    if (loadMoreContainer) loadMoreContainer.style.display = show ? 'block' : 'none';
}

function renderSearchResults(data, append = false) {
    const container = getSearchResultContainer();
    if (!container) return;

    const books = data?.books || [];

    if (!append) {
        container.innerHTML = '';
    }

    if (books.length === 0 && !append) {
        container.innerHTML = `
            <div class="empty-state">
                <iconify-icon icon="line-md:search" class="empty-icon"></iconify-icon>
                <div class="empty-state-text">未找到结果</div>
            </div>
        `;
        updateSearchHeader(0);
        toggleLoadMore(false);
        return;
    }

    const html = books.map(book => {
        const safeName = (book.book_name || '').replace(/"/g, '&quot;');
        const safeAuthor = (book.author || '').replace(/"/g, '&quot;');
        const abstract = book.abstract || '暂无简介';
        const statusBadge = book.status ? `<span class="status-badge ongoing">${book.status}</span>` : '';
        const cover = book.cover_url ? `src="${book.cover_url}"` : '';

        return `
            <div class="search-item" data-book-id="${book.book_id}" data-book-name="${safeName}">
                <img class="search-cover" ${cover} alt="${safeName}">
                <div class="search-info">
                    <div class="search-title">${book.book_name}</div>
                    <div class="search-meta">
                        ${safeAuthor}
                        <span>|</span>
                        <span>${(book.word_count || 0).toLocaleString()}字</span>
                        <span>|</span>
                        <span>${book.chapter_count || 0}章</span>
                        ${statusBadge}
                    </div>
                    <div class="search-desc-wrapper">
                        <div class="search-desc collapsed">${abstract}</div>
                        <button class="desc-toggle" type="button" data-action="toggle-desc" title="展开/收起">
                            <iconify-icon icon="line-md:chevron-down"></iconify-icon>
                        </button>
                    </div>
                </div>
                <div class="search-actions">
                    <button class="btn btn-primary btn-sm" data-action="download">下载</button>
                    <button class="btn btn-secondary btn-sm" data-action="queue">添加到队列</button>
                </div>
            </div>
        `;
    }).join('');

    if (append) {
        container.insertAdjacentHTML('beforeend', html);
    } else {
        container.innerHTML = html;
    }

    const totalLoaded = container.querySelectorAll('.search-item').length;
    updateSearchHeader(totalLoaded);
}

async function performSearch(append = false) {
    if (searchState.loading) return;
    searchState.loading = true;

    const keyword = searchState.keyword;
    const offset = append ? searchState.offset : 0;

    const searchBtn = document.getElementById('searchBtn');
    if (searchBtn && !append) {
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<span class="loading-spinner"></span> 搜索中...';
    }

    Logger.logKey('msg_search_start');

    try {
        const result = await api.search(keyword, offset);
        if (result.success) {
            renderSearchResults(result.data, append);
            Logger.logKey('msg_search_success');
            const added = result.data?.books?.length || 0;
            searchState.offset = offset + added;
            searchState.hasMore = !!result.data?.has_more;
            toggleLoadMore(searchState.hasMore);
        } else {
            Toast.error(result.message || '搜索失败');
            Logger.logKey('msg_search_empty');
            if (!append) {
                renderSearchResults({ books: [] }, false);
            }
        }
    } catch (e) {
        Toast.error('搜索请求失败: ' + e.message);
        Logger.log(`搜索失败: ${e.message}`, 'error');
    } finally {
        searchState.loading = false;
        if (searchBtn && !append) {
            searchBtn.disabled = false;
            searchBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> 搜索';
        }
    }
}

// ===================== 搜索功能 =====================

async function handleSearch() {
    const keyword = document.getElementById('searchKeyword')?.value.trim();
    if (!keyword) {
        Toast.warning('请输入搜索关键词');
        return;
    }

    searchState.keyword = keyword;
    searchState.offset = 0;
    searchState.hasMore = false;

    await performSearch(false);
}

async function handleLoadMoreSearchResults() {
    if (!searchState.keyword || !searchState.hasMore) return;
    await performSearch(true);
}

function clearSearchResults() {
    const container = getSearchResultContainer();
    if (container) container.innerHTML = '';
    updateSearchHeader(0);
    toggleLoadMore(false);
    searchState.keyword = '';
    searchState.offset = 0;
    searchState.hasMore = false;
}

// ===================== 下载处理 =====================

async function handleDownload(bookId, bookName) {
    const resolvedBookId = normalizeBookId(bookId || getInputBookId());
    if (!resolvedBookId) {
        Toast.warning('请输入书籍ID或链接');
        return;
    }

    const savePath = document.getElementById('savePath')?.value.trim();
    const fileFormat = getSelectedFormat();

    if (!savePath) {
        Toast.warning('请选择保存路径');
        handleSelectFolder();
        return;
    }

    const task = {
        book_id: resolvedBookId,
        save_path: savePath,
        file_format: fileFormat
    };

    const result = await api.download(task);
    if (result.success) {
        Toast.success(`开始下载: ${bookName || resolvedBookId}`);
        Logger.logKey('msg_download_start', bookName || resolvedBookId);
    } else {
        Toast.error(result.message || '下载启动失败');
        Logger.logKey('msg_download_failed', bookName || resolvedBookId);
    }
}

async function handleAddToQueue(bookId, bookName) {
    const resolvedBookId = normalizeBookId(bookId || getInputBookId());
    if (!resolvedBookId) {
        Toast.warning('请输入书籍ID或链接');
        return;
    }

    const savePath = document.getElementById('savePath')?.value.trim();

    if (!savePath) {
        Toast.warning('请先选择保存路径');
        handleSelectFolder();
        return;
    }

    const task = {
        book_id: resolvedBookId,
        book_name: bookName || resolvedBookId,
        save_path: savePath,
        file_format: getSelectedFormat()
    };

    QueueManager.add(task);
    Logger.logKey('msg_queue_added', bookName || resolvedBookId);
}

async function handleCancel() {
    const status = await api.getStatus();
    if (status.is_downloading) {
        ConfirmDialog.show('确定取消当前下载？', async () => {
            const result = await api.cancel();
            if (result.success) {
                Toast.info('下载已取消');
                Logger.log('下载已取消', 'warning');
            } else {
                Toast.error('取消失败');
            }
        }, { title: '取消下载', confirmText: '确定取消', confirmClass: 'btn-danger' });
    } else {
        Toast.info('没有正在进行的下载');
    }
}

function handleClear() {
    const input = document.getElementById('bookId');
    if (input) input.value = '';

    const inlineConfirm = document.getElementById('inlineConfirmContainer');
    if (inlineConfirm) inlineConfirm.style.display = 'none';

    Toast.info('已重置');
}

async function handleBrowse() {
    await handleSelectFolder();
}

async function handleStartQueueDownload() {
    const queue = QueueManager.getLocalQueue();
    if (queue.length === 0) {
        Toast.warning('队列为空');
        return;
    }

    const savePath = document.getElementById('savePath')?.value.trim();
    if (!savePath) {
        Toast.warning('请先选择保存路径');
        handleSelectFolder();
        return;
    }

    const bookIds = queue.map(t => t.book_id);
    const fileFormat = getSelectedFormat();

    const result = await api.request('/api/batch-download', {
        method: 'POST',
        body: JSON.stringify({
            book_ids: bookIds,
            save_path: savePath,
            file_format: fileFormat
        })
    });

    if (result.success) {
        Toast.success(result.message);
        QueueManager.clear();
    } else {
        Toast.error(result.message || '批量下载启动失败');
    }
}

function handleClearQueue() {
    QueueManager.clear();
}

async function handleLoadFromFile(e) {
    const file = e.target.files[0];
    if (!file) return;

    const savePath = document.getElementById('savePath')?.value.trim();
    if (!savePath) {
        Toast.warning('请先选择保存路径');
        handleSelectFolder();
        e.target.value = '';
        return;
    }

    try {
        const text = await file.text();
        const lines = text.split('\n').map(l => l.trim()).filter(l => l);
        const bookIds = [];

        for (const line of lines) {
            const match = line.match(/fanqienovel\.com\/page\/(\d+)/);
            if (match) {
                bookIds.push(match[1]);
            } else if (/^\d+$/.test(line)) {
                bookIds.push(line);
            }
        }

        if (bookIds.length > 0) {
            Toast.success(`成功解析 ${bookIds.length} 个书籍ID`);
            for (const bookId of bookIds) {
                QueueManager.add({ book_id: bookId, save_path: savePath, file_format: getSelectedFormat() });
            }
        } else {
            Toast.error('未能解析到有效的书籍ID');
        }
    } catch (err) {
        Toast.error('读取文件失败: ' + err.message);
    }

    e.target.value = '';
}

// ===================== 队列管理 =====================

function renderQueue() {
    QueueManager.render();
}

function initQueueListInteractions() {
    const container = document.getElementById('queueList');
    if (!container) return;

    container.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;

        if (btn.title === '移除') {
            const id = parseFloat(btn.closest('.queue-item')?.dataset.id);
            if (id) QueueManager.remove(id);
        }
    });
}

// ===================== 版本信息 =====================

async function fetchVersion() {
    try {
        const data = await api.request('/api/version');
        if (data.success) {
            const versionEl = document.getElementById('currentVersion');
            if (versionEl) versionEl.textContent = data.version;
        }
    } catch (e) {
        console.error('获取版本信息失败:', e);
    }
}

export {
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
    handleLoadMoreSearchResults,
    getSelectedFormat
};
