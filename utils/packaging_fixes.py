# -*- coding: utf-8 -*-
"""
打包兼容性修复模块
解决PyInstaller打包后的运行时问题
"""

import sys
import os
import asyncio
import threading
from pathlib import Path


def fix_frozen_path():
    """修复打包后的路径问题"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller临时目录
            base_path = sys._MEIPASS
        else:
            # 其他打包工具
            base_path = os.path.dirname(sys.executable)

        # 添加到Python路径
        if base_path not in sys.path:
            sys.path.insert(0, base_path)

        return base_path
    else:
        # 开发环境
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fix_config_path():
    """修复配置文件路径"""
    base_path = fix_frozen_path()

    # 尝试多个可能的配置文件位置
    config_paths = [
        os.path.join(base_path, 'config', 'fanqie.json'),
        os.path.join(base_path, 'fanqie.json'),
        os.path.join(os.path.dirname(base_path), 'config', 'fanqie.json'),
    ]

    for config_path in config_paths:
        if os.path.exists(config_path):
            return config_path

    # 如果都找不到，返回默认路径
    return config_paths[0]


def fix_asyncio_policy():
    """修复异步事件循环策略问题"""
    try:
        # Windows下设置事件循环策略
        if sys.platform == 'win32':
            # 避免在打包环境中出现事件循环问题
            if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            elif hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        # 静默处理异常，不影响程序启动
        pass


def fix_threading_issues():
    """修复多线程相关问题"""
    try:
        # 设置线程名称前缀，便于调试
        threading.current_thread().name = "MainThread"

        # 确保主线程有正确的事件循环
        if sys.platform == 'win32' and getattr(sys, 'frozen', False):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    asyncio.set_event_loop(asyncio.new_event_loop())
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass


def apply_all_fixes():
    """应用所有兼容性修复"""
    try:
        fix_frozen_path()
        fix_asyncio_policy()
        fix_threading_issues()
        return True
    except Exception as e:
        print(f"应用兼容性修复时出错: {e}")
        return False


# 自动应用修复（导入时执行）
if __name__ != "__main__":
    apply_all_fixes()