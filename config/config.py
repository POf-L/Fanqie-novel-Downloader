# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置
使用本地配置文件 fanqie.json
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

# 本地配置文件路径
LOCAL_CONFIG_JSON = os.path.join(os.path.dirname(__file__), 'fanqie.json')


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


def _load_local_config() -> Optional[Dict]:
    """从本地 fanqie.json 文件加载配置

    Returns:
        本地配置字典，失败返回None
    """
    try:
        if os.path.exists(LOCAL_CONFIG_JSON):
            with open(LOCAL_CONFIG_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 验证配置格式
            if isinstance(data, dict) and ('api_sources' in data or 'endpoints' in data or 'config' in data):
                return data
        else:
            print(f"警告: 本地配置文件不存在: {LOCAL_CONFIG_JSON}")
    except Exception as e:
        print(f"读取本地配置文件失败: {e}")

    return None


def load_config() -> Dict:
    """加载配置，使用本地 fanqie.json 文件

    Raises:
        ConfigLoadError: 无法获取本地配置时抛出异常
    """
    print("正在加载本地配置...")

    # 尝试加载本地配置
    local_config = _load_local_config()

    if not local_config:
        raise ConfigLoadError(
            "无法加载配置！请检查本地配置文件。\n"
            f"配置文件路径: {LOCAL_CONFIG_JSON}\n"
            "请确保 fanqie.json 文件存在且格式正确。"
        )

    # 从本地配置中提取各部分
    api_sources = local_config.get('api_sources', [])
    endpoints = local_config.get('endpoints', {})
    config_params = local_config.get('config', {})

    if not api_sources:
        raise ConfigLoadError("本地配置无效：缺少 api_sources")

    if not endpoints:
        raise ConfigLoadError("本地配置无效：缺少 endpoints")

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
