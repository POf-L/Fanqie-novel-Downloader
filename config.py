# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置
所有节点和配置必须通过远程服务器获取
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

# 远程配置URL - 所有配置必须从此处获取
REMOTE_CONFIG_URL = "https://qbin.me/r/fpoash/"
_LOCAL_CONFIG_FILE = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

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

# 本地固定的 API 端点配置（参考 http://49.232.137.12/docs）
LOCAL_ENDPOINTS = {
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


def load_remote_config() -> Dict:
    """从远程 URL 加载配置 - 远程仅控制节点和下载参数，endpoints 使用本地配置"""
    print(t("config_fetching", REMOTE_CONFIG_URL))
    
    # 默认配置结构
    config = {
        "api_base_url": "",
        "api_sources": [],
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
        "endpoints": LOCAL_ENDPOINTS  # 使用本地固定端点
    }

    try:
        response = requests.get(REMOTE_CONFIG_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if "config" not in data:
            print(t("config_invalid_format"))
            return config
            
        remote_conf = data["config"]
        
        # 更新基础配置
        config.update({
            "api_base_url": remote_conf.get("api_base_url", ""),
            "request_timeout": remote_conf.get("request_timeout", config["request_timeout"]),
            "max_retries": remote_conf.get("max_retries", config["max_retries"]),
            "connection_pool_size": remote_conf.get("connection_pool_size", config["connection_pool_size"]),
            "max_workers": remote_conf.get("max_workers", config["max_workers"]),
            "download_delay": remote_conf.get("download_delay", config["download_delay"]),
            "retry_delay": remote_conf.get("retry_delay", config["retry_delay"]),
            "download_enabled": remote_conf.get("download_enabled", config["download_enabled"]),
            "verbose_logging": remote_conf.get("verbose_logging", config["verbose_logging"]),
            "request_rate_limit": remote_conf.get("request_rate_limit", config["request_rate_limit"]),
            "api_rate_limit": remote_conf.get("api_rate_limit", config["api_rate_limit"]),
            "rate_limit_window": remote_conf.get("rate_limit_window", config["rate_limit_window"]),
            "async_batch_size": remote_conf.get("async_batch_size", config["async_batch_size"]),
        })

        # 如果仅提供 request_rate_limit，则同步为下载间隔
        if config.get("request_rate_limit") is not None and "download_delay" not in remote_conf:
            try:
                config["download_delay"] = float(config["request_rate_limit"])
            except (TypeError, ValueError):
                pass

        # 兼容：api_base_url = "auto"
        if isinstance(config.get("api_base_url"), str) and config["api_base_url"].strip().lower() == "auto":
            config["api_base_url"] = ""
        
        # endpoints 使用本地配置，不从远程覆盖

        # 解析多接口配置（从远程获取）
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

        config["api_sources"] = _dedupe_sources(sources)

        # 读取本地偏好（手动指定优先）
        local_pref = _load_local_pref()
        mode = str(local_pref.get("api_base_url_mode", "auto") or "auto").lower()
        pref_url = _normalize_base_url(str(local_pref.get("api_base_url", "") or ""))
        if mode == "manual" and pref_url:
            config["api_base_url"] = pref_url
            
        # 记录远程元信息（若存在）
        if isinstance(data.get("version"), str):
            config["remote_version"] = data["version"]
        if isinstance(data.get("update_time"), str):
            config["remote_update_time"] = data["update_time"]

        print(t("config_success", config['api_base_url'] or "auto"))
        return config
            
    except requests.exceptions.RequestException as e:
        print(t("config_fail", str(e)))
        print(t("config_server_error"))
    except json.JSONDecodeError as e:
        print(t("config_json_error", str(e)))
    except Exception as e:
        print(t("config_fail", str(e)))
    
    return config

CONFIG = load_remote_config()

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
