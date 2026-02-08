# -*- coding: utf-8 -*-
"""
仓库配置管理模块
提供统一的仓库配置获取和验证功能，支持错误回退机制
"""

import os
import re
import importlib
import sys
from typing import Tuple, Optional, Callable

# 导入配置常量（带异常处理）
try:
    from config.watermark_config import NETWORK_CONFIG, REPO_CONFIG, SECURITY_CONFIG
    CONFIG_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 配置文件不可用: {e}，使用默认配置")
    CONFIG_AVAILABLE = False
    # 默认配置
    NETWORK_CONFIG = {
        'TIMEOUT': 10,           # 请求超时时间（秒）
        'MAX_RETRIES': 3,        # 最大重试次数
        'BASE_DELAY': 1,         # 基础延迟时间（秒）
        'API_LIMIT_DELAY': 5,    # API限制时的额外延迟（秒）
        'USER_AGENT': 'Fanqie-novel-Downloader/1.0'  # 用户代理
    }
    REPO_CONFIG = {
        'DEFAULT_REPO': "POf-L/Fanqie-novel-Downloader",
        'MAX_REPO_LENGTH': 100,
        'MIN_REPO_LENGTH': 3,
    }
    SECURITY_CONFIG = {
        'DANGEROUS_CHARS': [';', '&', '|', '`', '$', '(', ')', '<', '>', '"', "'", '\\'],
        'ENABLE_SECURITY_CHECK': True,
    }

# 默认仓库配置（向后兼容）
DEFAULT_REPO = REPO_CONFIG['DEFAULT_REPO']


def validate_repo_format(repo: str) -> bool:
    """验证仓库格式是否有效
    
    Args:
        repo: 仓库名称，格式应为 owner/repo
        
    Returns:
        bool: 格式是否有效
    """
    if not repo or not isinstance(repo, str):
        return False
    
    # 检查基本格式
    if '/' not in repo or len(repo.split('/')) != 2:
        return False
    
    # 检查字符有效性（GitHub 仓库名规则）
    return bool(re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', repo))


def validate_repo_exists(repo: str) -> bool:
    """验证仓库是否真实存在（可选的GitHub API验证）
    
    Args:
        repo: 仓库名称，格式应为 owner/repo
        
    Returns:
        bool: 仓库是否存在
    """
    if not validate_repo_format(repo):
        return False
    
    try:
        import requests
        import time
        
        url = f"https://api.github.com/repos/{repo}"
        
        # 使用配置常量的统一重试机制和错误处理
        max_retries = NETWORK_CONFIG['MAX_RETRIES']
        base_delay = NETWORK_CONFIG['BASE_DELAY']
        timeout = NETWORK_CONFIG['TIMEOUT']
        api_limit_delay = NETWORK_CONFIG['API_LIMIT_DELAY']
        user_agent = NETWORK_CONFIG['USER_AGENT']
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url, 
                    timeout=timeout,
                    headers={'User-Agent': user_agent}
                )
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 404:
                    return False
                elif response.status_code == 403:
                    # API限制，等待更长时间
                    if attempt < max_retries - 1:
                        time.sleep(base_delay * (2 ** attempt) + api_limit_delay)
                        continue
                    # API限制时假设存在，避免阻塞
                    print("⚠️ GitHub API 限制，假设仓库存在")
                    return True
                else:
                    # 其他HTTP错误
                    if attempt < max_retries - 1:
                        time.sleep(base_delay * (2 ** attempt))
                        continue
                    print(f"⚠️ GitHub API 返回状态码 {response.status_code}，假设仓库存在")
                    return True
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                print("⚠️ 网络超时，假设仓库存在以避免阻塞")
                return True
                
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                print("⚠️ 网络连接错误，假设仓库存在以避免阻塞")
                return True
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(base_delay)
                    continue
                print(f"⚠️ 网络请求异常: {e}，假设仓库存在以避免阻塞")
                return True
                
    except ImportError:
        print("⚠️ requests 模块不可用，跳过仓库存在性验证")
        return True
    except Exception as e:
        print(f"⚠️ 仓库验证过程中发生意外错误: {e}，假设仓库存在以避免阻塞")
        return True


def validate_repo_security(repo: str) -> bool:
    """增强的仓库安全性验证
    
    Args:
        repo: 待验证的仓库名称
        
    Returns:
        bool: 是否通过安全验证
    """
    if not repo or not isinstance(repo, str):
        return False
    
    # 使用配置文件中的长度限制
    max_length = REPO_CONFIG['MAX_REPO_LENGTH']
    min_length = REPO_CONFIG['MIN_REPO_LENGTH']
    
    # 长度检查
    if len(repo.strip()) > max_length or len(repo.strip()) < min_length:
        return False
    
    # 检查危险字符，防止注入攻击
    if SECURITY_CONFIG['ENABLE_SECURITY_CHECK']:
        dangerous_chars = SECURITY_CONFIG['DANGEROUS_CHARS']
        if any(char in repo for char in dangerous_chars):
            return False
    
    # 检查是否包含路径遍历字符
    if '..' in repo:
        return False
    
    # 检查斜杠数量是否超过预期（格式应为 owner/repo）
    if repo.count('/') > 1:
        return False
    
    return True


def _get_env_repo() -> str:
    """统一的环境变量获取函数
    
    Returns:
        str: 环境变量中的仓库名称，如果不存在则返回空字符串
    """
    try:
        repo = os.environ.get("FANQIE_GITHUB_REPO", "").strip()
        
        # 增强的安全性检查
        if not validate_repo_security(repo):
            if repo:  # 只有在确实有值但不安全时才警告
                print("⚠️ 环境变量仓库名称存在安全风险或格式无效")
            return ""
            
        return repo
    except Exception as e:
        print(f"⚠️ 读取环境变量时发生错误: {e}")
        return ""


def _detect_circular_import(module_path: str) -> bool:
    """检测是否会造成循环导入

    使用更精确的检测机制，避免误报

    Args:
        module_path: 要导入的模块路径

    Returns:
        bool: 如果会造成循环导入返回True
    """
    try:
        # 检查模块是否正在初始化中
        if module_path in sys.modules:
            module = sys.modules[module_path]
            if (hasattr(module, '__spec__') and
                module.__spec__ and
                module.__spec__._initializing):
                return True

        # 更精确的调用栈分析
        frame = sys._getframe(1)
        caller_module = frame.f_globals.get('__name__')

        # 检查直接的循环导入关系
        if caller_module and caller_module in module_path and module_path in caller_module:
            return True

    except Exception:
        # 如果检测过程出错，保守地认为无循环导入
        pass

    return False


def _read_config_repo() -> Optional[str]:
    """安全地读取配置模块中的仓库信息
    
    使用延迟导入和异常处理避免循环导入风险
    
    Returns:
        Optional[str]: 仓库名称，失败时返回None
    """
    try:
        module_source = None

        # 首先尝试从环境变量获取配置路径
        config_path = os.environ.get("FANQIE_CONFIG_PATH", "config")

        # 兼容：若传入的是包名（如 config），优先尝试其 config 子模块
        candidate_modules = [config_path]
        if "." not in config_path:
            candidate_modules.insert(0, f"{config_path}.config")

        # CI 构建可注入 version.py，优先使用其仓库信息
        candidate_modules.insert(0, "version")

        for module_path in candidate_modules:
            if _detect_circular_import(module_path):
                print(f"⚠️ 检测到潜在的循环导入风险: {module_path}，跳过")
                continue

            try:
                module = importlib.import_module(module_path)
            except ImportError:
                continue

            repo = getattr(module, '__github_repo__', None)
            if repo:
                module_source = module_path
                os.environ["FANQIE_REPO_MODULE_SOURCE"] = module_source
                return repo

        return None
    except Exception as e:
        print(f"⚠️ 读取配置文件时发生意外错误: {e}")
        return None


def get_repo_from_config() -> str:
    """从配置模块获取仓库信息
    
    Returns:
        str: 仓库名称，失败时返回默认仓库
    """
    repo = _read_config_repo()
    
    if repo and validate_repo_format(repo):
        return repo
    elif repo:
        print(f"⚠️ 配置中的仓库格式无效: {repo}，使用默认仓库")
    
    return DEFAULT_REPO


def get_repo_from_env() -> str:
    """从环境变量获取仓库信息
    
    Returns:
        str: 仓库名称，失败时返回默认仓库
    """
    env_repo = _get_env_repo()
    
    if not env_repo:
        return DEFAULT_REPO
    
    if validate_repo_format(env_repo):
        return env_repo
    else:
        print(f"⚠️ 环境变量仓库格式无效: {env_repo}，使用默认仓库")
        return DEFAULT_REPO


def _validate_and_format_repo(repo: str, source: str) -> Optional[str]:
    """验证仓库格式并返回有效值
    
    Args:
        repo: 待验证的仓库名称
        source: 来源描述（用于错误消息）
        
    Returns:
        Optional[str]: 验证通过返回仓库名称，失败返回None
    """
    if not repo:
        return None
        
    if validate_repo_format(repo):
        return repo
    else:
        print(f"⚠️ {source}仓库格式无效: {repo}")
        return None


def _try_get_repo_from_source(source_name: str, get_repo_func: Callable[[], Optional[str]]) -> Tuple[Optional[str], str]:
    """尝试从指定源获取仓库配置
    
    Args:
        source_name: 源名称（用于错误消息）
        get_repo_func: 获取仓库的函数，应返回Optional[str]
        
    Returns:
        Tuple[Optional[str], str]: (仓库名称或None, 源名称)
    """
    try:
        repo = get_repo_func()
        if repo and validate_repo_format(repo):
            return repo, source_name
        elif repo:
            print(f"⚠️ {source_name}仓库格式无效: {repo}")
    except Exception as e:
        print(f"⚠️ 读取{source_name}时发生错误: {e}")
    
    return None, source_name


def get_effective_repo() -> Tuple[str, str]:
    """获取有效的仓库配置
    
    优先级: 环境变量 > 配置文件 > 默认值
    
    Returns:
        Tuple[str, str]: (仓库名称, 来源说明)
    """
    # 尝试环境变量
    repo, source = _try_get_repo_from_source("环境变量", lambda: _get_env_repo() or None)
    if repo:
        return repo, source
    
    # 尝试配置文件
    repo, source = _try_get_repo_from_source("配置文件", _read_config_repo)
    if repo:
        module_source = os.environ.get("FANQIE_REPO_MODULE_SOURCE", "").strip()
        if module_source == "version":
            return repo, "version.py"
        if module_source.endswith(".config"):
            return repo, "config.config"
        return repo, source
    
    # 使用默认值
    return DEFAULT_REPO, "默认值"


def get_repo_url(repo: str = None) -> str:
    """获取仓库的 GitHub URL
    
    Args:
        repo: 仓库名称，如果为 None 则使用有效仓库
        
    Returns:
        str: GitHub 仓库 URL
    """
    if not repo:
        repo, _ = get_effective_repo()
    
    return f"https://github.com/{repo}"


def safe_get_repo() -> str:
    """安全地获取仓库配置，确保始终返回有效值
    
    Returns:
        str: 有效的仓库名称
    """
    repo, _ = get_effective_repo()
    return repo


# 向后兼容的函数
def get_github_repo() -> str:
    """获取 GitHub 仓库配置（向后兼容）"""
    return safe_get_repo()


# 导出的符号
__all__ = [
    'DEFAULT_REPO',
    'validate_repo_format',
    'validate_repo_exists',
    'validate_repo_security',
    '_detect_circular_import',
    '_get_env_repo',
    '_read_config_repo',
    'get_repo_from_config',
    'get_repo_from_env',
    '_validate_and_format_repo',
    '_try_get_repo_from_source',
    'get_effective_repo',
    'get_repo_url',
    'safe_get_repo',
    'get_github_repo',
]
