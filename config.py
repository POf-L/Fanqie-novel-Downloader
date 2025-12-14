# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置
"""

__version__ = "1.0.0"
__author__ = "Tomato Novel Downloader"
__description__ = "A modern novel downloader with GitHub auto-update support"
__github_repo__ = "POf-L/Fanqie-novel-Downloader"
__build_time__ = "2025-01-23 00:00:00 UTC"
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
import requests
import os
import json
import tempfile
from typing import Dict
from fake_useragent import UserAgent
from locales import t

REMOTE_CONFIG_URL = "https://qbin.me/r/fpoash/"
_LOCAL_CONFIG_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

DEFAULT_API_SOURCES = [
    {"name": "qkfqapi.vv9v.cn", "base_url": "http://qkfqapi.vv9v.cn"},
    {"name": "fq.shusan.cn", "base_url": "https://fq.shusan.cn"},
    {"name": "api.jkyai.top", "base_url": "https://api.jkyai.top"},
    {"name": "43.248.77.205:22222", "base_url": "http://43.248.77.205:22222"},
]

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

def _dedupe_sources(sources: list) -> list:
    seen = set()
    deduped = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        base_url = _normalize_base_url(s.get("base_url") or s.get("api_base_url") or "")
        if not base_url or base_url in seen:
            continue
        seen.add(base_url)
        name = (s.get("name") or s.get("id") or base_url).strip() if isinstance(s.get("name") or s.get("id") or base_url, str) else base_url
        deduped.append({"name": name, "base_url": base_url})
    return deduped

def load_remote_config() -> Dict:
    """从远程 URL 加载配置"""
    print(t("config_fetching", REMOTE_CONFIG_URL))
    
    default_config = {
        "api_base_url": "",
        "api_sources": DEFAULT_API_SOURCES.copy(),
        "request_timeout": 10,
        "max_retries": 3,
        "connection_pool_size": 10,
        "max_workers": 5,
        "download_delay": 0.5,
        "retry_delay": 2,
        "status_file": ".download_status.json",
        "download_enabled": True,
        "verbose_logging": False,
        "request_rate_limit": None,
        "api_rate_limit": None,
        "rate_limit_window": None,
        "async_batch_size": None,
        "endpoints": {
            "search": "/api/search",
            "detail": "/api/detail",
            "book": "/api/book",
            "directory": "/api/directory",
            "content": "/api/content",
            "chapter": "/api/chapter",
            "raw_full": "/api/raw_full",
            "comment": "/api/comment",
            "multi_content": "/api/content",
            "ios_content": "/api/ios/content",
            "ios_register": "/api/ios/register",
            "device_pool": "/api/device/pool",
            "device_register": "/api/device/register",
            "device_status": "/api/device/status"
        }
    }

    try:
        response = requests.get(REMOTE_CONFIG_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if "config" in data:
            remote_conf = data["config"]
            
            # 更新基础配置
            default_config.update({
                "api_base_url": remote_conf.get("api_base_url", ""),
                "request_timeout": remote_conf.get("request_timeout", default_config["request_timeout"]),
                "max_retries": remote_conf.get("max_retries", default_config["max_retries"]),
                "connection_pool_size": remote_conf.get("connection_pool_size", default_config["connection_pool_size"]),
                "max_workers": remote_conf.get("max_workers", default_config["max_workers"]),
                "download_delay": remote_conf.get("download_delay", default_config["download_delay"]),
                "retry_delay": remote_conf.get("retry_delay", default_config["retry_delay"]),
                "download_enabled": remote_conf.get("download_enabled", default_config["download_enabled"]),
                "verbose_logging": remote_conf.get("verbose_logging", default_config["verbose_logging"]),
                "request_rate_limit": remote_conf.get("request_rate_limit", default_config["request_rate_limit"]),
                "api_rate_limit": remote_conf.get("api_rate_limit", default_config["api_rate_limit"]),
                "rate_limit_window": remote_conf.get("rate_limit_window", default_config["rate_limit_window"]),
                "async_batch_size": remote_conf.get("async_batch_size", default_config["async_batch_size"]),
            })

            # 如果仅提供 request_rate_limit，则同步为下载间隔
            if default_config.get("request_rate_limit") is not None and "download_delay" not in remote_conf:
                try:
                    default_config["download_delay"] = float(default_config["request_rate_limit"])
                except (TypeError, ValueError):
                    pass

            # 兼容：api_base_url = "auto"
            if isinstance(default_config.get("api_base_url"), str) and default_config["api_base_url"].strip().lower() == "auto":
                default_config["api_base_url"] = ""
            
            # 更新端点配置 (映射 tomato_endpoints -> endpoints)
            if "tomato_endpoints" in remote_conf:
                default_config["endpoints"] = remote_conf["tomato_endpoints"]

            # 解析多接口配置（新格式：api_sources / api_base_urls）
            sources = []
            if isinstance(remote_conf.get("api_sources"), list):
                for item in remote_conf["api_sources"]:
                    if isinstance(item, str):
                        sources.append({"name": item, "base_url": item})
                    elif isinstance(item, dict):
                        base_url = item.get("base_url") or item.get("api_base_url") or item.get("url") or ""
                        if base_url:
                            sources.append({"name": item.get("name") or item.get("id") or base_url, "base_url": base_url})

            if isinstance(remote_conf.get("api_base_urls"), list):
                for url in remote_conf["api_base_urls"]:
                    if isinstance(url, str) and url.strip():
                        sources.append({"name": url.strip(), "base_url": url.strip()})

            if isinstance(remote_conf.get("api_base_url"), str) and remote_conf.get("api_base_url", "").strip():
                api_base = remote_conf["api_base_url"].strip()
                if api_base.lower() != "auto":
                    sources.append({"name": api_base, "base_url": api_base})

            # 远程配置优先，这样远程的友好名称会覆盖默认的 URL 名称
            default_config["api_sources"] = _dedupe_sources(sources + default_config.get("api_sources", []))

            # 读取本地偏好（手动指定优先）
            local_pref = _load_local_pref()
            mode = str(local_pref.get("api_base_url_mode", "auto") or "auto").lower()
            pref_url = _normalize_base_url(str(local_pref.get("api_base_url", "") or ""))
            if mode == "manual" and pref_url:
                default_config["api_base_url"] = pref_url
                
            # 记录远程元信息（若存在）
            if isinstance(data.get("version"), str):
                default_config["remote_version"] = data["version"]
            if isinstance(data.get("update_time"), str):
                default_config["remote_update_time"] = data["update_time"]

            print(t("config_success", default_config['api_base_url']))
            return default_config
            
    except Exception as e:
        print(t("config_fail", str(e)))
        # 如果获取失败且用户要求不保留硬编码，这里可能导致程序无法运行
        # 但为了保证程序基本结构完整，返回空配置或报错
        print(t("config_server_error"))
    
    return default_config

CONFIG = load_remote_config()

print_lock = threading.Lock()

_UA_SINGLETON = None
_UA_LOCK = threading.Lock()
_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
]

def _get_ua() -> UserAgent:
    global _UA_SINGLETON
    if _UA_SINGLETON is None:
        with _UA_LOCK:
            if _UA_SINGLETON is None:
                try:
                    _UA_SINGLETON = UserAgent(fallback=random.choice(_DEFAULT_USER_AGENTS))
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
        user_agent = random.choice(_DEFAULT_USER_AGENTS)

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