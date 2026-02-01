/* ===================== 番茄小说下载器 - 主入口 ===================== */

import Toast from './toast.js';
import TaskManager from './unified_task.js';
import { ConfirmDialog, DuplicateDialog, FolderBrowser } from './dialogs.js';
import AppState from './state.js';
import VersionManager from './version.js';
import Logger from './logger.js';
import api from './api.js';
import { adjustPathFontSize, initPathAutoResize } from './path.js';
import TabSystem from './tabs.js';
import ApiSelector from './api_selector.js';
import { initializeUI, initTabSystem, initApiSourceControls, initApiSourceControlsLazy, initChapterModalEvents, initSearchListInteractions, initWindowControls, initVersionCheck } from './ui.js';
import { loadSettings, saveSettings, updateSliderValue, handleSelectFolder, handleSavePathChange } from './settings.js';

import { fetchVersion, handleAddToQueue, handleBrowse, handleCancel, handleClear, handleClearQueue, handleDownload, handleLoadFromFile, handleSearch, handleStartQueueDownload, initQueueListInteractions, renderQueue, clearSearchResults, handleLoadMoreSearchResults } from './app_handlers.js';
import { closeChapterModal, openChapterModal, showUpdateModal } from './app_modals.js';

// 全局导出供HTML调用
window.Toast = Toast;
window.TaskManager = TaskManager;
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
window.ApiSelector = ApiSelector;
window.initializeUI = initializeUI;
window.loadSettings = loadSettings;
window.saveSettings = saveSettings;
window.updateSliderValue = updateSliderValue;
window.handleSelectFolder = handleSelectFolder;
window.handleSavePathChange = handleSavePathChange;

AppState.loadQueue = function() {
    TaskManager.getTasks();
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
        }

        await new Promise(resolve => setTimeout(resolve, interval));
    }

    console.log('[DEBUG] 连接服务器超时');
    if (loadingText) loadingText.textContent = '连接服务器超时';
    if (loadingHint) loadingHint.textContent = '请检查服务器是否正常启动';
    return false;
}

// ===================== 主初始化函数 =====================

async function initializeApp() {
    console.log('[DEBUG] 开始初始化应用...');

    const loadingOverlay = document.getElementById('loadingOverlay');

    try {
        const serverReady = await waitForServerReady();

        if (!serverReady) {
            console.error('[ERROR] 服务器未就绪');
            if (loadingText) loadingText.textContent = '服务器连接失败';
            if (loadingHint) loadingHint.textContent = '请检查服务器是否正常运行';
            return;
        }

        console.log('[DEBUG] 初始化UI...');
        await initializeUI();

        console.log('[DEBUG] 初始化版本检查...');
        initVersionCheck();

        console.log('[DEBUG] 初始化完成');
        if (loadingOverlay) {
            loadingOverlay.style.opacity = '0';
            setTimeout(() => loadingOverlay.style.display = 'none', 300);
        }

    } catch (error) {
        console.error('[ERROR] 初始化失败:', error);
        if (loadingText) loadingText.textContent = '初始化失败';
        if (loadingHint) loadingHint.textContent = error.message || '未知错误';
    }
}

// ===================== 页面加载完成后启动 =====================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

// ===================== 页面卸载时清理 =====================

window.addEventListener('beforeunload', () => {
    console.log('[DEBUG] 清理资源...');
    TaskManager.stopStatusPolling();
});

// ===================== 防止意外关闭 =====================

window.addEventListener('unload', () => {
    console.log('[DEBUG] 页面卸载');
});

export { TaskManager };
