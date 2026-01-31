/* ===================== 设置页面功能 ===================== */

import Toast from './toast.js';
import AppState from './state.js';
import Logger from './logger.js';
import api from './api.js';
import { FolderBrowser } from './dialogs.js';
import { adjustPathFontSize } from './path.js';

const SETTINGS_META = {
    max_workers: {
        rangeId: 'setting_max_workers_range',
        numberId: 'setting_max_workers',
        valueId: 'setting_max_workers_value',
        defaultValue: 30,
        type: 'int',
        scale: 1
    },
    request_rate_limit: {
        rangeId: 'setting_request_rate_limit_range',
        numberId: 'setting_request_rate_limit',
        valueId: 'setting_request_rate_limit_value',
        defaultValue: 0.02,
        type: 'float',
        scale: 1000,
        format: (v) => v.toFixed(2)
    },
    connection_pool_size: {
        rangeId: 'setting_connection_pool_size_range',
        numberId: 'setting_connection_pool_size',
        valueId: 'setting_connection_pool_size_value',
        defaultValue: 200,
        type: 'int',
        scale: 1
    },
    async_batch_size: {
        rangeId: 'setting_async_batch_size_range',
        numberId: 'setting_async_batch_size',
        valueId: 'setting_async_batch_size_value',
        defaultValue: 50,
        type: 'int',
        scale: 1
    },
    max_retries: {
        rangeId: 'setting_max_retries_range',
        numberId: 'setting_max_retries',
        valueId: 'setting_max_retries_value',
        defaultValue: 3,
        type: 'int',
        scale: 1
    },
    request_timeout: {
        rangeId: 'setting_request_timeout_range',
        numberId: 'setting_request_timeout',
        valueId: 'setting_request_timeout_value',
        defaultValue: 30,
        type: 'int',
        scale: 1
    },
    api_rate_limit: {
        rangeId: 'setting_api_rate_limit_range',
        numberId: 'setting_api_rate_limit',
        valueId: 'setting_api_rate_limit_value',
        defaultValue: 50,
        type: 'int',
        scale: 1
    },
    rate_limit_window: {
        rangeId: 'setting_rate_limit_window_range',
        numberId: 'setting_rate_limit_window',
        valueId: 'setting_rate_limit_window_value',
        defaultValue: 1.0,
        type: 'float',
        scale: 10,
        format: (v) => v.toFixed(1)
    }
};

function clamp(value, min, max) {
    let result = value;
    if (Number.isFinite(min)) result = Math.max(min, result);
    if (Number.isFinite(max)) result = Math.min(max, result);
    return result;
}

function getElements(meta) {
    const range = document.getElementById(meta.rangeId);
    const number = document.getElementById(meta.numberId);
    const value = document.getElementById(meta.valueId);
    return { range, number, value };
}

function formatValue(meta, value) {
    if (meta.format) return meta.format(value);
    if (meta.type === 'float') return String(value);
    return String(Math.round(value));
}

function setSettingValue(key, value) {
    const meta = SETTINGS_META[key];
    if (!meta) return;

    const { range, number, value: valueEl } = getElements(meta);
    const scale = meta.scale || 1;

    const min = number?.min ? parseFloat(number.min) : (range?.min ? parseFloat(range.min) / scale : undefined);
    const max = number?.max ? parseFloat(number.max) : (range?.max ? parseFloat(range.max) / scale : undefined);

    let nextValue = meta.type === 'int' ? Math.round(value) : parseFloat(value);
    if (!Number.isFinite(nextValue)) nextValue = meta.defaultValue;
    nextValue = clamp(nextValue, min, max);

    if (number) number.value = meta.type === 'int' ? String(Math.round(nextValue)) : String(nextValue);
    if (range) {
        if (number?.max && scale !== 1) {
            const adjustedMax = parseFloat(number.max) * scale;
            if (Number.isFinite(adjustedMax)) range.max = String(adjustedMax);
        }
        range.value = String(nextValue * scale);
    }
    if (valueEl) valueEl.textContent = formatValue(meta, nextValue);
}

function readSettingValue(key) {
    const meta = SETTINGS_META[key];
    if (!meta) return undefined;
    const { number } = getElements(meta);
    if (!number) return meta.defaultValue;
    const raw = meta.type === 'int' ? parseInt(number.value, 10) : parseFloat(number.value);
    return Number.isFinite(raw) ? raw : meta.defaultValue;
}

function bindSettingControl(key) {
    const meta = SETTINGS_META[key];
    const { range, number } = getElements(meta);
    if (!range || !number) return;

    const scale = meta.scale || 1;

    range.addEventListener('input', () => {
        const value = parseFloat(range.value) / scale;
        setSettingValue(key, value);
    });

    number.addEventListener('input', () => {
        const value = meta.type === 'int' ? parseInt(number.value, 10) : parseFloat(number.value);
        setSettingValue(key, value);
    });
}

function showSettingsMessage(message, isError = false) {
    const el = document.getElementById('settingsMessage');
    if (!el) return;
    el.textContent = message;
    el.style.display = 'block';
    el.style.color = isError ? 'var(--danger)' : 'var(--text-secondary)';
}

async function loadSettings() {
    const result = await api.getSettings();
    if (result.success && result.settings) {
        const settings = result.settings;
        Object.keys(SETTINGS_META).forEach((key) => {
            const value = settings[key] ?? SETTINGS_META[key].defaultValue;
            setSettingValue(key, value);
        });
    } else {
        Object.keys(SETTINGS_META).forEach((key) => {
            setSettingValue(key, SETTINGS_META[key].defaultValue);
        });
    }
}

async function saveSettings() {
    const settings = {};
    Object.keys(SETTINGS_META).forEach((key) => {
        settings[key] = readSettingValue(key);
    });

    const result = await api.saveSettings(settings);
    if (result.success) {
        Toast.success('设置已保存');
        showSettingsMessage('设置已保存');
    } else {
        Toast.error(result.error || '保存设置失败');
        showSettingsMessage(result.error || '保存设置失败', true);
    }
}

async function resetSettings() {
    Object.keys(SETTINGS_META).forEach((key) => {
        setSettingValue(key, SETTINGS_META[key].defaultValue);
    });
    await saveSettings();
}

function initSettingsUI() {
    Object.keys(SETTINGS_META).forEach((key) => {
        bindSettingControl(key);
    });

    document.getElementById('saveSettingsBtn')?.addEventListener('click', saveSettings);
    document.getElementById('resetSettingsBtn')?.addEventListener('click', resetSettings);

    loadSettings();
}

function updateSliderValue(id, value) {
    const el = document.getElementById(id + 'Value');
    if (el) el.textContent = value;
}

async function handleSelectFolder() {
    const result = await FolderBrowser.show(async (path) => {
        const res = await api.setSavePath(path);
        if (res.success) {
            AppState.setSavePath(path);
            const pathInput = document.getElementById('savePath');
            if (pathInput) {
                pathInput.value = path;
                adjustPathFontSize(pathInput);
            }
            Toast.success('保存路径已更新: ' + path);
        }
    });
}

async function handleSavePathChange() {
    const pathInput = document.getElementById('savePath');
    if (!pathInput) return;

    const path = pathInput.value.trim();
    if (!path) return;

    const res = await api.setSavePath(path);
    if (res.success) {
        AppState.setSavePath(path);
        Logger.logKey('msg_save_path_updated', path);
    }
}

export {
    loadSettings,
    saveSettings,
    updateSliderValue,
    handleSelectFolder,
    handleSavePathChange,
    initSettingsUI,
    resetSettings
};
