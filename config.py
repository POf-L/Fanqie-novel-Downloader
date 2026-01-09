# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置
完全依赖远程配置，无网络则无法使用
"""

__version__ = "1.1.0"
__author__ = "Tomato Novel Downloader"
__description__ = "A modern novel downloader with GitHub auto-update support"
__github_repo__ = "POf-L/Fanqie-novel-Downloader"
__build_time__ = "2025-12-13 21:00:00"
__build_channel__ = "custom"

try:
    import version as _ver
except Exception:
    _ver = None
else:
    __version__ = getattr(_ver, "__version__", __version__)
    __author__ = getattr(_ver, "__author__", __author__)
    __description__ = getattr(_ver, "__description__", __description__)
    __github_repo__ = getattr(_ver, "__github_repo__", __github_repo__)
    __build_time__ = getattr(_ver, "__build_time__", __build_time__)
    __build_channel__ = getattr(_ver, "__build_channel__", __build_channel__)

import random
import threading
import os
import json
import tempfile
import time
from datetime import datetime
from typing import Dict, Optional
from fake_useragent import UserAgent

_LOCAL_CONFIG_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

# 远程配置相关常量
REMOTE_CONFIG_URL = "https://lllllllllllllllllllllll.rth1.xyz/fanqie.json"
REMOTE_CONFIG_CACHE_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_remote_config_cache.json')
REMOTE_CONFIG_CACHE_TTL = 3600  # 缓存有效期：1小时


class ConfigLoadError(Exception):
    """配置加载失败异常"""
    pass


def _normalize_base_url(url: str) -> str:
    url = (url or "").strip()
    return url.rstrip('/')


def _load_local_pref() -> Dict:
    try:
        if os.path.exists(_LOCAL_CONFIG_FILE):
            with open(_LOCAL_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _load_remote_config() -> Optional[Dict]:
    """从远程URL加载配置，支持缓存

    Returns:
        远程配置字典，失败返回None
    """
    # 1. 检查缓存是否有效
    if os.path.exists(REMOTE_CONFIG_CACHE_FILE):
        try:
            with open(REMOTE_CONFIG_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            cache_time = cache.get('_cache_time', 0)
            if time.time() - cache_time < REMOTE_CONFIG_CACHE_TTL:
                return cache.get('data')
        except Exception:
            pass

    # 2. 从远程获取配置
    try:
        import requests
        # 先尝试直连（禁用代理），再尝试使用系统代理
        for proxies in [{'http': None, 'https': None}, None]:
            try:
                response = requests.get(REMOTE_CONFIG_URL, timeout=10, proxies=proxies)
                if response.status_code == 200:
                    data = response.json()
                    # 验证配置格式
                    if isinstance(data, dict) and ('api_sources' in data or 'endpoints' in data or 'config' in data):
                        # 保存到缓存
                        cache = {'_cache_time': time.time(), 'data': data}
                        try:
                            with open(REMOTE_CONFIG_CACHE_FILE, 'w', encoding='utf-8') as f:
                                json.dump(cache, f, ensure_ascii=False)
                        except Exception:
                            pass
                        return data
            except Exception:
                continue
    except Exception:
        pass

    # 3. 尝试读取过期缓存作为备用（离线模式）
    if os.path.exists(REMOTE_CONFIG_CACHE_FILE):
        try:
            with open(REMOTE_CONFIG_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            return cache.get('data')
        except Exception:
            pass

    return None


def load_config() -> Dict:
    """加载配置，完全依赖远程配置

    Raises:
        ConfigLoadError: 无法获取远程配置时抛出异常
    """
    print("正在从云端加载配置...")

    # 尝试加载远程配置
    remote_config = _load_remote_config()

    if not remote_config:
        raise ConfigLoadError(
            "无法加载配置！请检查网络连接。\n"
            f"配置地址: {REMOTE_CONFIG_URL}\n"
            "应用需要网络连接才能正常使用。"
        )

    # 从远程配置中提取各部分
    api_sources = remote_config.get('api_sources', [])
    endpoints = remote_config.get('endpoints', {})
    config_params = remote_config.get('config', {})

    if not api_sources:
        raise ConfigLoadError("远程配置无效：缺少 api_sources")

    if not endpoints:
        raise ConfigLoadError("远程配置无效：缺少 endpoints")

    config = {
        "api_base_url": "",
        "api_sources": api_sources.copy() if isinstance(api_sources, list) else [],
        "request_timeout": config_params.get("request_timeout", 30),
        "max_retries": config_params.get("max_retries", 3),
        "connection_pool_size": config_params.get("connection_pool_size", 100),
        "max_workers": config_params.get("max_workers", 10),
        "download_delay": config_params.get("request_rate_limit", 0.05),
        "retry_delay": 2,
        "status_file": ".download_status.json",
        "download_enabled": config_params.get("download_enabled", True),
        "verbose_logging": False,
        "request_rate_limit": config_params.get("request_rate_limit", 0.05),
        "api_rate_limit": config_params.get("api_rate_limit", 20),
        "rate_limit_window": config_params.get("rate_limit_window", 1.0),
        "async_batch_size": config_params.get("async_batch_size", 50),
        "endpoints": endpoints if isinstance(endpoints, dict) else {}
    }

    # 读取本地偏好（手动/自动选择均可复用）
    local_pref = _load_local_pref()
    mode = str(local_pref.get("api_base_url_mode", "auto") or "auto").lower()
    pref_url = _normalize_base_url(str(local_pref.get("api_base_url", "") or ""))
    if mode in ("manual", "auto") and pref_url:
        config["api_base_url"] = pref_url

    print(f"配置加载成功，API节点数: {len(config['api_sources'])}")
    return config


# 加载配置（启动时执行）
try:
    CONFIG = load_config()
except ConfigLoadError as e:
    print(f"\n错误: {e}\n")
    CONFIG = None

print_lock = threading.Lock()

_UA_SINGLETON = None
_UA_LOCK = threading.Lock()


def _get_ua() -> UserAgent:
    global _UA_SINGLETON
    if _UA_SINGLETON is None:
        with _UA_LOCK:
            if _UA_SINGLETON is None:
                try:
                    _UA_SINGLETON = UserAgent()
                except Exception:
                    _UA_SINGLETON = None
    return _UA_SINGLETON


def get_headers() -> Dict[str, str]:
    user_agent = None
    try:
        ua = _get_ua()
        if ua is not None:
            user_agent = ua.chrome if random.choice(["chrome", "edge"]) == "chrome" else ua.edge
    except Exception:
        user_agent = None

    if not user_agent:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://fanqienovel.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json"
    }


__all__ = [
    "CONFIG",
    "ConfigLoadError",
    "print_lock",
    "get_headers",
    "__version__",
    "__author__",
    "__description__",
    "__github_repo__",
    "__build_time__",
    "__build_channel__"
]
