# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置
API文档: https://qkfqapi.vv9v.cn/docs
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
from locales import t

_LOCAL_CONFIG_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

# 远程配置相关常量
REMOTE_CONFIG_URL = "https://lllllllllllllllllllllll.rth1.xyz/fanqie.json"
REMOTE_CONFIG_CACHE_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_remote_config_cache.json')
REMOTE_CONFIG_CACHE_TTL = 3600  # 缓存有效期：1小时

# 硬编码的 API 源配置
HARDCODED_API_SOURCES = [
    {"name": "中国|陕西省|西安市|电信", "base_url": "http://103.236.91.147:9999"},
    {"name": "中国|浙江省|宁波市|电信(HTTPS)", "base_url": "https://qkfqapi.vv9v.cn"},
    {"name": "中国|浙江省|宁波市|电信", "base_url": "http://qkfqapi.vv9v.cn"},
    {"name": "中国|北京市|腾讯云", "base_url": "http://49.232.137.12"},
    {"name": "中国|江苏省|常州市|电信", "base_url": "http://43.248.77.205:22222"},
    {"name": "日本|东京", "base_url": "https://fq.shusan.cn"}
]

# 硬编码的配置参数
HARDCODED_CONFIG = {
    "max_workers": 10,              # 并发线程数，提高下载速度
    "max_retries": 3,
    "request_timeout": 30,
    "request_rate_limit": 0.05,     # 请求间隔降低到50ms，允许快速并发
    "connection_pool_size": 100,
    "api_rate_limit": 20,           # 每秒最大请求数
    "rate_limit_window": 1.0,
    "async_batch_size": 50,         # 增大批量处理大小
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
        response = requests.get(REMOTE_CONFIG_URL, timeout=5)
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
        pass

    # 3. 尝试读取过期缓存作为备用
    if os.path.exists(REMOTE_CONFIG_CACHE_FILE):
        try:
            with open(REMOTE_CONFIG_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            return cache.get('data')
        except Exception:
            pass

    return None

# API 端点配置 - 对接 https://qkfqapi.vv9v.cn/docs
LOCAL_ENDPOINTS = {
    "search": "/api/search",       # 搜索书籍 (key, tab_type, offset)
    "detail": "/api/detail",       # 获取书籍详情 (book_id)
    "book": "/api/book",           # 获取书籍目录 (book_id)
    "directory": "/api/directory", # 获取简化目录 (fq_id)
    "content": "/api/content",     # 内容接口 (tab=小说/听书/短剧/漫画/批量, item_id/book_id)
    "chapter": "/api/chapter",     # 简化章节接口 (item_id) - 备用
    # 新增端点
    "raw_full": "/api/raw_full",           # 原始内容 (item_id)
    "ios_content": "/api/ios/content",     # iOS内容 (item_id)
    "ios_register": "/api/ios/register",   # iOS设备注册
    "device_pool": "/api/device/pool",     # 设备池状态
    "device_register": "/api/device/register",  # 设备注册 (platform)
    "device_status": "/api/device/status",      # 设备状态 (platform)
    "manga_progress": "/api/manga/progress",    # 漫画进度 (task_id)
}


def load_config() -> Dict:
    """加载配置，优先使用远程配置，失败时回退到本地配置"""
    print(t("config_loading_local"))

    # 尝试加载远程配置
    remote_config = _load_remote_config()

    # 根据远程配置或本地配置构建最终配置
    if remote_config:
        api_sources = remote_config.get('api_sources', HARDCODED_API_SOURCES)
        endpoints = remote_config.get('endpoints', LOCAL_ENDPOINTS)
        config_params = remote_config.get('config', HARDCODED_CONFIG)
    else:
        api_sources = HARDCODED_API_SOURCES
        endpoints = LOCAL_ENDPOINTS
        config_params = HARDCODED_CONFIG

    config = {
        "api_base_url": "",
        "api_sources": api_sources.copy() if isinstance(api_sources, list) else HARDCODED_API_SOURCES.copy(),
        "request_timeout": config_params.get("request_timeout", HARDCODED_CONFIG["request_timeout"]),
        "max_retries": config_params.get("max_retries", HARDCODED_CONFIG["max_retries"]),
        "connection_pool_size": config_params.get("connection_pool_size", HARDCODED_CONFIG["connection_pool_size"]),
        "max_workers": config_params.get("max_workers", HARDCODED_CONFIG["max_workers"]),
        "download_delay": config_params.get("request_rate_limit", HARDCODED_CONFIG["request_rate_limit"]),
        "retry_delay": 2,
        "status_file": ".download_status.json",
        "download_enabled": config_params.get("download_enabled", HARDCODED_CONFIG["download_enabled"]),
        "verbose_logging": False,
        "request_rate_limit": config_params.get("request_rate_limit", HARDCODED_CONFIG["request_rate_limit"]),
        "api_rate_limit": config_params.get("api_rate_limit", HARDCODED_CONFIG["api_rate_limit"]),
        "rate_limit_window": config_params.get("rate_limit_window", HARDCODED_CONFIG["rate_limit_window"]),
        "async_batch_size": config_params.get("async_batch_size", HARDCODED_CONFIG["async_batch_size"]),
        "endpoints": endpoints if isinstance(endpoints, dict) else LOCAL_ENDPOINTS
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

def export_config_to_file(filepath: str = "fanqie.txt") -> str:
    """导出当前配置到文件

    Args:
        filepath: 导出文件路径，默认为 fanqie.txt

    Returns:
        导出的文件路径
    """
    config_data = {
        "version": __version__,
        "updated_at": datetime.now().isoformat(),
        "api_sources": HARDCODED_API_SOURCES,
        "endpoints": LOCAL_ENDPOINTS,
        "config": HARDCODED_CONFIG
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
    return filepath

__all__ = [
    "CONFIG",
    "print_lock",
    "get_headers",
    "export_config_to_file",
    "__version__",
    "__author__",
    "__description__",
    "__github_repo__",
    "__build_time__",
    "__build_channel__"
]
