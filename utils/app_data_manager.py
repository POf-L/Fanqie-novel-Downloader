# -*- coding: utf-8 -*-
"""
应用数据目录管理器
统一管理所有生成文件的存储位置
"""

import os
import sys
from pathlib import Path


class AppDataManager:
    """应用数据目录管理器 - 将所有生成文件放到程序同名子目录中"""

    def __init__(self):
        self._data_dir = None
        self._app_name = None

    def get_app_name(self) -> str:
        """获取程序名称（不含扩展名）"""
        if self._app_name is None:
            if getattr(sys, 'frozen', False):
                executable = os.path.basename(sys.executable)
            else:
                executable = os.path.basename(sys.argv[0])
            
            # 去除扩展名
            self._app_name = os.path.splitext(executable)[0]
        
        return self._app_name

    def get_base_dir(self) -> str:
        """获取程序运行目录"""
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                return os.path.dirname(sys.executable)
            else:
                return os.path.dirname(os.path.abspath(__file__))
        else:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def get_data_dir(self) -> str:
        """获取应用数据目录（程序同名子目录）"""
        if self._data_dir is None:
            base_dir = self.get_base_dir()
            app_name = self.get_app_name()
            self._data_dir = os.path.join(base_dir, app_name)
            
            # 确保目录存在
            os.makedirs(self._data_dir, exist_ok=True)
        
        return self._data_dir

    def get_config_dir(self) -> str:
        """获取配置文件目录（数据目录下的config子目录）"""
        config_dir = os.path.join(self.get_data_dir(), 'config')
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def get_downloads_dir(self) -> str:
        """获取下载文件目录（数据目录下的novels子目录）"""
        downloads_dir = os.path.join(self.get_data_dir(), 'novels')
        os.makedirs(downloads_dir, exist_ok=True)
        return downloads_dir

    def get_logs_dir(self) -> str:
        """获取日志目录（数据目录下的logs子目录）"""
        logs_dir = os.path.join(self.get_data_dir(), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir

    def get_window_config_path(self) -> str:
        """获取窗口配置文件路径"""
        return os.path.join(self.get_data_dir(), 'fanqie_window_config.json')

    def get_app_config_path(self) -> str:
        """获取应用配置文件路径"""
        return os.path.join(self.get_config_dir(), 'fanqie_novel_downloader_config.json')

    def get_fanqie_config_path(self) -> str:
        """获取番茄小说配置文件路径"""
        return os.path.join(self.get_config_dir(), 'fanqie.json')


# 全局单例
_data_manager = None


def get_data_manager() -> AppDataManager:
    """获取全局数据管理器实例"""
    global _data_manager
    if _data_manager is None:
        _data_manager = AppDataManager()
    return _data_manager


# 便捷函数
def get_data_dir() -> str:
    """获取数据目录"""
    return get_data_manager().get_data_dir()


def get_config_dir() -> str:
    """获取配置目录"""
    return get_data_manager().get_config_dir()


def get_downloads_dir() -> str:
    """获取下载目录"""
    return get_data_manager().get_downloads_dir()


def get_window_config_path() -> str:
    """获取窗口配置文件路径"""
    return get_data_manager().get_window_config_path()


def get_app_config_path() -> str:
    """获取应用配置文件路径"""
    return get_data_manager().get_app_config_path()


def get_fanqie_config_path() -> str:
    """获取番茄小说配置文件路径"""
    return get_data_manager().get_fanqie_config_path()
