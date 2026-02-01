# -*- coding: utf-8 -*-
"""Web应用共享状态和工具函数"""

import os
import sys
import json
from pathlib import Path

# 添加父目录到路径
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        _base_path = sys._MEIPASS
    else:
        _base_path = os.path.dirname(sys.executable)
    if _base_path not in sys.path:
        sys.path.insert(0, _base_path)
else:
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)


def get_config_dir():
    """获取配置文件目录（使用统一数据目录）"""
    try:
        from utils.app_data_manager import get_config_dir as _get_config_dir
        return _get_config_dir()
    except ImportError:
        # 如果导入失败，使用原有逻辑
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        config_dir = os.path.join(base_dir, 'config')
        os.makedirs(config_dir, exist_ok=True)
        return config_dir


def _get_config_file_path():
    """获取配置文件路径"""
    try:
        from utils.app_data_manager import get_app_config_path
        return get_app_config_path()
    except ImportError:
        return os.path.join(get_config_dir(), 'fanqie_novel_downloader_config.json')

CONFIG_FILE = _get_config_file_path()


def _read_local_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_local_config(updates: dict) -> bool:
    try:
        cfg = _read_local_config()
        cfg.update(updates or {})
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_default_download_path():
    """获取默认下载路径（使用统一数据目录）"""
    try:
        from utils.app_data_manager import get_downloads_dir
        return get_downloads_dir()
    except ImportError:
        # 如果导入失败，使用原有逻辑
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        downloads = os.path.join(base_dir, 'novels')
        
        if not os.path.exists(downloads):
            try:
                os.makedirs(downloads, exist_ok=True)
            except:
                downloads = base_dir
        
        return downloads


# 导入队列（延迟导入避免循环依赖）
download_queue = None
_status_dict = {'is_downloading': False, 'progress': 0, 'message': '', 'current_book': ''}
_status_lock = __import__('threading').Lock()


def get_status():
    """获取下载状态"""
    with _status_lock:
        return _status_dict.copy()


def update_status(**kwargs):
    """更新下载状态"""
    with _status_lock:
        for key, value in kwargs.items():
            if key in _status_dict:
                _status_dict[key] = value


def init_download_queue():
    """初始化下载队列（延迟导入）"""
    global download_queue
    if download_queue is None:
        from queue import Queue
        download_queue = Queue()
