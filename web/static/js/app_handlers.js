/* ===================== 应用功能处理（搜索/下载/队列/版本） ===================== */

import Toast from './toast.js';
import TaskManager from './unified_task.js';
import { ConfirmDialog } from './dialogs.js';
import Logger from './logger.js';
import api from './api.js';
import { handleSelectFolder } from './settings.js';

const searchState = {
    keyword: '',
    offset: 0,
    hasMore: false,
    loading: false,
    statusFilter: ''
};

function detectInputType(input) {
    if (!input) return 'keyword';
    
    const text = String(input).trim();
    
    // 检查是否为数字ID
    if (/^\d+$/.test(text)) {
        return 'id';
    }
    
    // 检查是否为URL
    if (text.includes('fanqienovel.com') || text.includes('http')) {
        const match = text.match(/\/page\/(\d+)/);
        if (match) {
            return 'url';
        }
    }
    
    return 'keyword';
}

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
    const radio = document.querySelector('input[name="format"]:checked');
    if (radio?.value) return radio.value;
    return 'txt';
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
        const statusBadge = book.status ? `<span class="status-badge ${book.status === '已完结' ? 'completed' : 'ongoing'}">${book.status}</span>` : '';
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
    const statusFilter = searchState.statusFilter;

    const searchBtn = document.getElementById('searchBtn');
    if (searchBtn && !append) {
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<span class="loading-spinner"></span> 搜索中...';
    }

    Logger.logKey('msg_search_start');

    try {
        const result = await api.search(keyword, offset);
        if (result.success) {
            let books = result.data?.books || [];
            
            if (statusFilter) {
                books = books.filter(book => book.status === statusFilter);
            }
            
            renderSearchResults({ books }, append);
            Logger.logKey('msg_search_success');
            
            searchState.offset = offset + books.length;
            searchState.hasMore = !!result.data?.has_more;
            toggleLoadMore(searchState.hasMore && books.length > 0);
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
            searchBtn.innerHTML = '<iconify-icon icon="line-md:search"></iconify-icon>';
        }
    }
}

async function handleSearch() {
    const keyword = document.getElementById('searchKeyword')?.value.trim();
    const statusFilter = document.getElementById('statusFilter')?.value || '';
    
    if (!keyword) {
        Toast.warning('请输入搜索关键词');
        return;
    }

    const inputType = detectInputType(keyword);
    console.log(`[DEBUG] 输入类型: ${inputType}, 内容: ${keyword}`);

    if (inputType === 'id' || inputType === 'url') {
        const bookId = normalizeBookId(keyword);
        console.log(`[DEBUG] 识别为ID: ${bookId}`);
        
        try {
            const result = await api.getBookInfo(bookId);
            if (result.success && result.data) {
                const book = result.data;
                renderSearchResults({
                    books: [book]
                }, false);
                searchState.hasMore = false;
                toggleLoadMore(false);
                Logger.logKey('msg_search_success');
                return;
            }
        } catch (e) {
            console.error('获取书籍信息失败:', e);
        }
    }

    searchState.keyword = keyword;
    searchState.statusFilter = statusFilter;
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
    searchState.statusFilter = '';
    searchState.offset = 0;
    searchState.hasMore = false;
}

async function handleDownload(bookId, bookName) {
    try {
        const result = await api.getBookInfo(bookId);
        if (!result.success || !result.data) {
            Toast.error('获取书籍信息失败');
            return;
        }

        const book = result.data;
        await openChapterModal(book);
    } catch (e) {
        Toast.error('获取书籍信息失败: ' + e.message);
        Logger.log(`获取书籍信息失败: ${e.message}`, 'error');
    }
}

function handleAddToQueue(bookId, bookName) {
    const task = {
        book_id: bookId,
        book_name: bookName
    };
    TaskManager.add(task);
}

async function handleBrowse() {
    handleSelectFolder();
}

function handleCancel() {
    const bookIdInput = document.getElementById('bookId');
    const downloadBtn = document.getElementById('downloadBtn');
    const cancelBtn = document.getElementById('cancelBtn');
    
    if (bookIdInput) bookIdInput.value = '';
    if (downloadBtn) downloadBtn.style.display = 'inline-flex';
    if (cancelBtn) cancelBtn.style.display = 'none';
    
    AppState.setCurrentBook(null);
}

function handleClear() {
    handleCancel();
    AppState.clearChapterSelection();
}

async function handleStartQueueDownload() {
    const tasks = TaskManager.getTasks();
    if (tasks.length === 0) {
        Toast.warning('队列为空');
        return;
    }

    const savePath = AppState.getSavePath();
    if (!savePath) {
        Toast.warning('请先设置保存路径');
        return;
    }

    try {
        const format = getSelectedFormat();
        const result = await api.request('/api/batch-download', {
            method: 'POST',
            body: JSON.stringify({
                book_ids: tasks.map(t => t.book_id),
                save_path: savePath,
                file_format: format
            })
        });

        if (result.success) {
            Toast.success('开始批量下载');
            Logger.logKey('msg_download_start');
        } else {
            Toast.error(result.message || '启动失败');
        }
    } catch (e) {
        Toast.error('启动失败: ' + e.message);
        Logger.log(`启动失败: ${e.message}`, 'error');
    }
}

function handleClearQueue() {
    ConfirmDialog.show({
        title: '清空队列',
        message: '确定要清空所有任务吗？',
        onConfirm: () => {
            TaskManager.clear();
        }
    });
}

async function handleLoadFromFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    try {
        const text = await file.text();
        const lines = text.split('\n')
            .map(line => line.trim())
            .filter(line => line && !line.startsWith('#'));

        if (lines.length === 0) {
            Toast.warning('文件中没有有效的书籍ID');
            return;
        }

        let addedCount = 0;
        for (const line of lines) {
            const bookId = normalizeBookId(line);
            if (bookId) {
                try {
                    const result = await api.getBookInfo(bookId);
                    if (result.success && result.data) {
                        const task = {
                            book_id: bookId,
                            book_name: result.data.book_name || bookId
                        };
                        TaskManager.add(task);
                        addedCount++;
                    }
                } catch (e) {
                    console.error(`获取书籍 ${bookId} 信息失败:`, e);
                }
            }
        }

        if (addedCount > 0) {
            Toast.success(`已添加 ${addedCount} 本书到队列`);
        } else {
            Toast.warning('没有添加任何书籍');
        }
    } catch (e) {
        Toast.error('读取文件失败: ' + e.message);
    }

    event.target.value = '';
}

function renderQueue() {
    TaskManager.render();
}

function initQueueListInteractions() {
    const container = document.getElementById('queueList');
    if (!container) return;

    container.addEventListener('click', (e) => {
        const action = e.target.closest('[data-action]');
        if (!action) return;

        const actionType = action.dataset.action;
        const item = action.closest('.queue-item');
        if (!item) return;

        const id = parseFloat(item.dataset.id);
        const bookId = item.dataset.bookId;

        switch (actionType) {
            case 'remove':
                if (id) {
                    TaskManager.remove(id);
                }
                break;
            case 'retry':
                if (bookId) {
                    TaskManager.updateTaskStatus(bookId, 'pending');
                    TaskManager.render();
                }
                break;
        }
    });
}

async function fetchVersion() {
    try {
        const result = await api.getVersion();
        if (result.success) {
            const currentVersion = result.data.current_version;
            const latestVersion = result.data.latest_version;
            
            if (currentVersion !== latestVersion) {
                showUpdateModal(currentVersion, latestVersion, result.data.description);
            }
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
    handleLoadMoreSearchResults
};
