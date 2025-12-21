# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置
API文档: http://49.232.137.12/docs
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
from typing import Dict
from fake_useragent import UserAgent
from locales import t

_LOCAL_CONFIG_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

# 硬编码的 API 源配置
HARDCODED_API_SOURCES = [
    {"name": "中国|浙江省|宁波市|电信", "base_url": "http://qkfqapi.vv9v.cn"},
    {"name": "中国|北京市|腾讯云", "base_url": "http://49.232.137.12"},
    {"name": "中国|江苏省|常州市|电信", "base_url": "http://43.248.77.205:22222"},
    {"name": "日本|东京", "base_url": "https://fq.shusan.cn"}
]

# 硬编码的配置参数
HARDCODED_CONFIG = {
    "max_workers": 2,
    "max_retries": 3,
    "request_timeout": 30,
    "request_rate_limit": 0.5,
    "connection_pool_size": 100,
    "api_rate_limit": 5,
    "rate_limit_window": 1.0,
    "async_batch_size": 30,
    "download_enabled": True
}

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

# API 端点配置 - 对接 http://49.232.137.12/docs
LOCAL_ENDPOINTS = {
    "search": "/api/search",       # 搜索书籍 (key, tab_type, offset)
    "detail": "/api/detail",       # 获取书籍详情 (book_id)
    "book": "/api/book",           # 获取书籍目录 (book_id)
    "directory": "/api/directory", # 获取简化目录 (fq_id)
    "content": "/api/content",     # 内容接口 (tab=小说/批量/下载, item_id/book_id)
}


def load_config() -> Dict:
    """加载硬编码配置"""
    print(t("config_loading_local"))
    
    config = {
        "api_base_url": "",
        "api_sources": HARDCODED_API_SOURCES.copy(),
        "request_timeout": HARDCODED_CONFIG["request_timeout"],
        "max_retries": HARDCODED_CONFIG["max_retries"],
        "connection_pool_size": HARDCODED_CONFIG["connection_pool_size"],
        "max_workers": HARDCODED_CONFIG["max_workers"],
        "download_delay": HARDCODED_CONFIG["request_rate_limit"],
        "retry_delay": 2,
        "status_file": ".download_status.json",
        "download_enabled": HARDCODED_CONFIG["download_enabled"],
        "verbose_logging": False,
        "request_rate_limit": HARDCODED_CONFIG["request_rate_limit"],
        "api_rate_limit": HARDCODED_CONFIG["api_rate_limit"],
        "rate_limit_window": HARDCODED_CONFIG["rate_limit_window"],
        "async_batch_size": HARDCODED_CONFIG["async_batch_size"],
        "endpoints": LOCAL_ENDPOINTS
    }

    # 读取本地偏好（手动/自动选择均可复用）
    local_pref = _load_local_pref()
    mode = str(local_pref.get("api_base_url_mode", "auto") or "auto").lower()
    pref_url = _normalize_base_url(str(local_pref.get("api_base_url", "") or ""))
    if mode in ("manual", "auto") and pref_url:
        config["api_base_url"] = pref_url

    print(t("config_success", config['api_base_url'] or "auto"))
    return config

CONFIG = load_config()

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
    "print_lock",
    "get_headers",
    "__version__",
    "__author__",
    "__description__",
    "__github_repo__",
    "__build_time__",
    "__build_channel__"
]
