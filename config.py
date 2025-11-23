# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置
"""

__version__ = "debug"
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
from typing import Dict
from fake_useragent import UserAgent

REMOTE_CONFIG_URL = "https://qbin.me/r/fpoash/"

def load_remote_config() -> Dict:
    """从远程 URL 加载配置"""
    print(f"正在获取最新的 API 配置: {REMOTE_CONFIG_URL}")
    
    default_config = {
        "api_base_url": "",
        "request_timeout": 10,
        "max_retries": 3,
        "connection_pool_size": 10,
        "max_workers": 5,
        "download_delay": 0.5,
        "retry_delay": 2,
        "status_file": ".download_status.json",
        "endpoints": {}
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
                "request_timeout": remote_conf.get("request_timeout", 10),
                "max_retries": remote_conf.get("max_retries", 3),
                "connection_pool_size": remote_conf.get("connection_pool_size", 100),
                "max_workers": remote_conf.get("max_workers", 2),
            })
            
            # 更新端点配置 (映射 tomato_endpoints -> endpoints)
            if "tomato_endpoints" in remote_conf:
                default_config["endpoints"] = remote_conf["tomato_endpoints"]
                
            print(f"成功加载配置，API 地址: {default_config['api_base_url']}")
            return default_config
            
    except Exception as e:
        print(f"获取远程配置失败: {str(e)}")
        # 如果获取失败且用户要求不保留硬编码，这里可能导致程序无法运行
        # 但为了保证程序基本结构完整，返回空配置或报错
        print("⚠️ 警告: 无法连接配置服务器，程序可能无法正常工作")
    
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
                    _UA_SINGLETON = UserAgent(cache=True, fallback=random.choice(_DEFAULT_USER_AGENTS))
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
