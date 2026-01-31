/* ===================== 番茄小说下载器 - 主入口 ===================== */
/* 此文件为模块化入口，实际功能在各模块文件中 */

import Toast from './toast.js';
import QueueManager from './queue.js';
import { ConfirmDialog, DuplicateDialog, FolderBrowser } from './dialogs.js';
import AppState from './state.js';
import VersionManager from './version.js';
import Logger from './logger.js';
import api from './api.js';
import { adjustPathFontSize, initPathAutoResize } from './path.js';
import TabSystem from './tabs.js';
import DownloadQueue from './download_queue.js';
import ApiSelector from './api_selector.js';
import { initializeUI, initTabSystem, initApiSourceControls, initApiSourceControlsLazy, initChapterModalEvents, initSearchListInteractions, initWindowControls, initVersionCheck } from './ui.js';
import { loadSettings, saveSettings, updateSliderValue, handleSelectFolder, handleSavePathChange } from './settings.js';

import { fetchVersion, handleAddToQueue, handleBrowse, handleCancel, handleClear, handleClearQueue, handleDownload, handleLoadFromFile, handleSearch, handleStartQueueDownload, initQueueListInteractions, renderQueue } from './app_handlers.js';
import { closeChapterModal, openChapterModal, showUpdateModal } from './app_modals.js';

// 全局导出供HTML调用
window.Toast = Toast;
window.QueueManager = QueueManager;
window.ConfirmDialog = ConfirmDialog;
window.DuplicateDialog = DuplicateDialog;
window.FolderBrowser = FolderBrowser;
window.AppState = AppState;
window.VersionManager = VersionManager;
window.Logger = Logger;
window.api = api;
window.adjustPathFontSize = adjustPathFontSize;
window.initPathAutoResize = initPathAutoResize;
window.TabSystem = TabSystem;
window.DownloadQueue = DownloadQueue;
window.ApiSelector = ApiSelector;
window.initializeUI = initializeUI;
window.loadSettings = loadSettings;
window.saveSettings = saveSettings;
window.updateSliderValue = updateSliderValue;
window.handleSelectFolder = handleSelectFolder;
window.handleSavePathChange = handleSavePathChange;

AppState.loadQueue = function() {
    QueueManager.getLocalQueue();
};

// ===================== 服务器就绪检查 =====================

async function waitForServerReady(maxAttempts = 30, interval = 500) {
    const loadingText = document.getElementById('loadingText');
    const loadingHint = document.getElementById('loadingHint');

    console.log('[DEBUG] 开始等待服务器就绪...');

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            if (loadingText) {
                loadingText.textContent = `正在连接服务器... (${attempt}/${maxAttempts})`;
            }

            console.log(`[DEBUG] 尝试连接服务器 (${attempt}/${maxAttempts})`);

            // 获取 token 并添加到 URL
            const token = AppState.getAccessToken();
            const url = token ? `/api/health?token=${token}` : '/api/health';

            console.log(`[DEBUG] 请求 URL: ${url}`);

            const response = await fetch(url, {
                method: 'GET',
                cache: 'no-cache'
            });

            console.log(`[DEBUG] 响应状态: ${response.status}`);

            if (response.ok) {
                const data = await response.json();
                console.log('[DEBUG] 响应数据:', data);
                if (data.status === 'ready') {
                    if (loadingText) loadingText.textContent = '服务器已就绪';
                    console.log('[DEBUG] 服务器就绪！');
                    return true;
                }
            } else {
                console.log(`[DEBUG] 响应失败: ${response.status} ${response.statusText}`);
            }
        } catch (e) {
            console.log(`[DEBUG] 请求异常: ${e.message}`);
            // 服务器还未启动，继续等待
        }

        await new Promise(resolve => setTimeout(resolve, interval));
    }

    console.log('[DEBUG] 连接服务器超时');
    if (loadingText) loadingText.textContent = '连接服务器超时';
    if (loadingHint) loadingHint.textContent = '请检查服务器是否正常启动';
    return false;
}

// ===================== 初始化 =====================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('[DEBUG] DOMContentLoaded 事件触发');
    Logger.logKey('msg_app_start');

    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    console.log('[DEBUG] URL token:', token ? '存在' : '不存在');

    if (token) {
        AppState.setAccessToken(token);
        Logger.logKey('msg_token_loaded');
        console.log('[DEBUG] Token 已设置到 AppState');
    }

    // 等待服务器就绪
    console.log('[DEBUG] 开始等待服务器就绪...');
    const serverReady = await waitForServerReady();

    if (!serverReady) {
        console.log('[DEBUG] 服务器未就绪，停止初始化');
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            const loadingText = document.getElementById('loadingText');
            const loadingHint = document.getElementById('loadingHint');
            if (loadingText) loadingText.textContent = '无法连接到服务器';
            if (loadingHint) loadingHint.textContent = '请重启应用或检查网络连接';
        }
        return;
    }

    console.log('[DEBUG] 服务器已就绪，开始初始化...');

    // 服务器就绪后，执行初始化
    console.log('[DEBUG] 调用 api.checkUpdate() 和 api.init()');
    const [updateResult, initSuccess] = await Promise.all([
        api.checkUpdate().catch((e) => {
            console.log('[DEBUG] checkUpdate 失败:', e);
            return { success: false };
        }),
        api.init().catch((e) => {
            console.log('[DEBUG] init 失败:', e);
            return { success: false };
        })
    ]);

    console.log('[DEBUG] checkUpdate 结果:', updateResult);
    console.log('[DEBUG] init 结果:', initSuccess);

    // 移除加载遮罩层
    console.log('[DEBUG] 移除加载遮罩层');
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
        setTimeout(() => {
            loadingOverlay.remove();
        }, 300);
    }

    console.log('[DEBUG] 初始化 UI...');
    if (updateResult.success && updateResult.has_update) {
        initializeUI(true);
        showUpdateModal(updateResult.data);
    } else {
        initializeUI(false);
        if (initSuccess) {
            Logger.logKey('msg_ready');
        } else {
            Logger.logKey('msg_init_partial');
            Logger.logKey('msg_check_network');
        }
    }

    console.log('[DEBUG] 初始化完成');
});

// 热键支持
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const downloadBtn = document.getElementById('downloadBtn');
        if (downloadBtn && downloadBtn.style.display !== 'none' && !downloadBtn.disabled) {
            handleAddToQueue();
        }
    }
});

// 窗口控制
initWindowControls();

// 轮询服务器状态
setInterval(async () => {
    const status = await api.getStatus();

    if (Array.isArray(status.messages) && status.messages.length > 0) {
        status.messages.forEach((msg) => {
            if (msg) Logger.log(msg, 'info');
        });
    }
    
    // 更新任务中心状态
    const statusTextMain = document.getElementById('statusTextMain');
    if (statusTextMain) {
        if (status.is_downloading) {
            statusTextMain.innerHTML = `<iconify-icon icon="line-md:loading-twotone-loop" class="spin"></iconify-icon> 下载中`;
        } else {
            statusTextMain.innerHTML = `<iconify-icon icon="line-md:confirm-circle"></iconify-icon>`;
        }
    }
    
    const bookNameMain = document.getElementById('bookNameMain');
    if (bookNameMain) {
        bookNameMain.textContent = status.book_name || '-';
    }
    
    const progressPercentMain = document.getElementById('progressPercentMain');
    if (progressPercentMain) {
        progressPercentMain.textContent = `${status.progress || 0}%`;
    }
    
    const progressFillMain = document.getElementById('progressFillMain');
    if (progressFillMain) {
        progressFillMain.style.width = `${status.progress || 0}%`;
    }
    
    const progressDetailInfo = document.getElementById('progressDetailInfo');
    if (progressDetailInfo) {
        if (status.total_chapters) {
            const done = status.downloaded_chapters || 0;
            progressDetailInfo.textContent = `${done} / ${status.total_chapters} 章节`;
        } else {
            progressDetailInfo.textContent = status.message || '等待任务开始...';
        }
    }
}, 1000);

// 导出全局函数
window.handleSearch = handleSearch;
window.handleDownload = handleDownload;
window.handleAddToQueue = handleAddToQueue;
window.handleCancel = handleCancel;
window.handleClear = handleClear;
window.handleBrowse = handleBrowse;
window.handleStartQueueDownload = handleStartQueueDownload;
window.handleClearQueue = handleClearQueue;
window.handleLoadFromFile = handleLoadFromFile;
window.openChapterModal = openChapterModal;
window.closeChapterModal = closeChapterModal;
window.renderQueue = renderQueue;
window.initQueueListInteractions = initQueueListInteractions;
window.fetchVersion = fetchVersion;
window.showUpdateModal = showUpdateModal;
