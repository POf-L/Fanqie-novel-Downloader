# -*- coding: utf-8 -*-
"""
配置管理模块 - 包含版本信息、全局配置和远程配置管理。
"""

__version__ = "1.0.0"
__author__ = "Tomato Novel Downloader"
__description__ = "A modern novel downloader with GitHub auto-update support"
__github_repo__ = "POf-L/Fanqie-novel-Downloader"
__build_time__ = "2025-01-23 00:00:00 UTC"
__build_channel__ = "custom"

try:
    import version as _ver  # type: ignore
except Exception:
    _ver = None
else:
    __version__ = getattr(_ver, "__version__", __version__)
    __author__ = getattr(_ver, "__author__", __author__)
    __description__ = getattr(_ver, "__description__", __description__)
    __github_repo__ = getattr(_ver, "__github_repo__", __github_repo__)
    __build_time__ = getattr(_ver, "__build_time__", __build_time__)
    __build_channel__ = getattr(_ver, "__build_channel__", __build_channel__)

import json
import random
import time
import threading
from typing import Dict, Optional

import requests
import urllib3
from fake_useragent import UserAgent

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()


# ===================== 远程配置管理器 =====================

class RemoteConfigManager:
    """远程配置管理器 - 从云端获取API配置"""
    
    # 远程配置URL列表（支持多个备用）
    REMOTE_URLS = [
        "https://qbin.me/r/fpoash/",
        # 可以添加更多备用URL
    ]
    
    def __init__(self):
        self._cache = None
        self._cache_time = 0
        self._cache_timeout = 3600  # 缓存1小时
        self._lock = threading.Lock()
    
    def fetch_remote_config(self, timeout: int = 10, strict: bool = False) -> Optional[Dict]:
        """
        从远程URL获取配置
        
        Args:
            timeout: 请求超时时间（秒）
            strict: 严格模式，失败时抛出异常
            
        Returns:
            配置字典或None
            
        Raises:
            RuntimeError: 严格模式下获取失败
        """
        # 检查缓存
        with self._lock:
            if self._cache and (time.time() - self._cache_time) < self._cache_timeout:
                return self._cache.copy()
        
        errors = []  # 记录所有错误
        
        # 尝试所有URL
        for url in self.REMOTE_URLS:
            try:
                response = requests.get(
                    url, 
                    timeout=timeout,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                
                if response.status_code == 200:
                    # 尝试解析JSON
                    try:
                        data = response.json()
                        
                        # 验证配置格式
                        if self._validate_config(data):
                            # 缓存配置
                            with self._lock:
                                self._cache = data
                                self._cache_time = time.time()
                            
                            return data
                        else:
                            errors.append(f"{url}: 配置格式验证失败")
                    except json.JSONDecodeError as e:
                        errors.append(f"{url}: JSON解析失败 - {str(e)}")
                        continue
                else:
                    errors.append(f"{url}: HTTP {response.status_code}")
                        
            except requests.Timeout:
                errors.append(f"{url}: 请求超时({timeout}秒)")
            except requests.ConnectionError:
                errors.append(f"{url}: 连接失败")
            except Exception as e:
                errors.append(f"{url}: {type(e).__name__} - {str(e)}")
        
        # 严格模式下抛出异常
        if strict:
            error_msg = "\n".join([f"  - {err}" for err in errors])
            raise RuntimeError(
                f"无法从任何远程服务器获取配置：\n{error_msg}\n\n"
                f"请检查：\n"
                f"1. 网络连接是否正常\n"
                f"2. 防火墙/代理设置\n"
                f"3. 远程配置服务器是否可用"
            )
        
        return None
    
    def _validate_config(self, data: Dict) -> bool:
        """验证配置格式是否正确"""
        if not isinstance(data, dict):
            return False
        
        # 检查必需字段
        config = data.get("config", {})
        if not isinstance(config, dict):
            return False
        
        # 检查关键字段
        required_fields = ["api_base_url", "tomato_endpoints"]
        for field in required_fields:
            if field not in config:
                return False
        
        return True
    
    def merge_config(self, base_config: Dict, remote_data: Dict) -> Dict:
        """将远程配置合并到基础配置"""
        if not remote_data or "config" not in remote_data:
            return base_config
        
        remote_config = remote_data.get("config", {})
        
        # 创建新配置（深拷贝）
        new_config = base_config.copy()
        
        # 合并配置项
        for key, value in remote_config.items():
            if isinstance(value, dict) and key in new_config and isinstance(new_config[key], dict):
                # 字典类型，递归合并
                new_config[key] = {**new_config[key], **value}
            else:
                # 直接覆盖
                new_config[key] = value
        
        return new_config
    
    def get_config_info(self, remote_data: Optional[Dict]) -> str:
        """获取配置信息摘要"""
        if not remote_data:
            return "未获取到远程配置"
        
        version = remote_data.get("version", "未知")
        update_time = remote_data.get("update_time", "未知")
        config = remote_data.get("config", {})
        api_base = config.get("api_base_url", "未知")
        
        return f"远程配置 v{version} (更新时间: {update_time}, API: {api_base})"


# 全局远程配置管理器实例
_remote_config_manager = RemoteConfigManager()


# ===================== 全局配置 =====================

# 基础配置（仅包含运行参数，不包含API配置）
_BASE_CONFIG = {
    "max_workers": 2,
    "max_retries": 3,
    "request_timeout": 30,
    "status_file": "chapter.json",
    "request_rate_limit": 0.5,
    "download_enabled": True,
    "verbose_logging": False,
    "async_batch_size": 30,
    "connection_pool_size": 100,
    "api_rate_limit": 5,
    "rate_limit_window": 1.0,
    "enable_remote_config": True,  # 是否启用远程配置
    "remote_config_timeout": 10    # 远程配置加载超时（秒）
}

# 全局配置（将在初始化时尝试从远程加载）
CONFIG = _BASE_CONFIG.copy()

print_lock = threading.Lock()

# 从远程加载配置（必须成功）
def _load_remote_config():
    """从远程加载配置，失败时抛出异常"""
    if not CONFIG.get("enable_remote_config", True):
        raise RuntimeError("远程配置已禁用，但本地无API配置可用")
    
    with print_lock:
        print("[配置] 正在从远程服务器获取API配置...")
    
    try:
        # 使用严格模式获取远程配置
        timeout = CONFIG.get("remote_config_timeout", 10)
        remote_data = _remote_config_manager.fetch_remote_config(timeout=timeout, strict=True)
        
        # 合并配置
        merged_config = _remote_config_manager.merge_config(CONFIG, remote_data)
        config_info = _remote_config_manager.get_config_info(remote_data)
        
        # 更新全局配置
        CONFIG.update(merged_config)
        
        with print_lock:
            print(f"[配置] ✓ {config_info}")
            
    except Exception as e:
        with print_lock:
            print(f"[配置] ✗ 远程配置加载失败: {str(e)}")
        raise RuntimeError(f"无法获取远程API配置，程序无法启动: {str(e)}")

# 初始化时加载远程配置
_load_remote_config()

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
    """生成请求头（优先使用 fake_useragent，失败时回退到本地列表）。"""
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
    "RemoteConfigManager",
    "__version__",
    "__author__",
    "__description__",
    "__github_repo__",
    "__build_time__",
    "__build_channel__"
]
