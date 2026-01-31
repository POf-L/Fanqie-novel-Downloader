"""
窗口位置管理器 - 保存/恢复窗口位置与大小
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional


class WindowPositionManager:
    """管理窗口位置的保存和恢复

    保存窗口位置到配置文件，并在下次启动时恢复
    """

    CONFIG_FILE = 'fanqie_window_config.json'
    POSITION_KEY = 'window_position'

    # 最小可见区域（像素）
    MIN_VISIBLE_SIZE = 100

    def __init__(self, config_dir: str = None):
        """
        初始化窗口位置管理器

        Args:
            config_dir: 配置文件存储目录，默认为程序所在目录
        """
        if config_dir:
            self.config_dir = config_dir
        else:
            # 获取程序所在目录
            if getattr(sys, 'frozen', False):
                # 打包环境
                if hasattr(sys, '_MEIPASS'):
                    self.config_dir = os.path.dirname(sys.executable)
                else:
                    self.config_dir = os.path.dirname(os.path.abspath(__file__))
            else:
                # 开发环境 - 使用项目根目录
                self.config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.config_file = os.path.join(self.config_dir, self.CONFIG_FILE)

    def save_position(self, x: int, y: int, width: int, height: int, maximized: bool = False) -> bool:
        """
        保存窗口位置到配置文件

        Args:
            x: 窗口左上角 X 坐标
            y: 窗口左上角 Y 坐标
            width: 窗口宽度
            height: 窗口高度
            maximized: 是否最大化

        Returns:
            是否保存成功
        """
        try:
            config = self._load_config()
            config[self.POSITION_KEY] = {
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'maximized': maximized
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def load_position(self) -> Optional[dict]:
        """
        加载保存的窗口位置

        Returns:
            {'x': int, 'y': int, 'width': int, 'height': int, 'maximized': bool} 或 None
        """
        try:
            config = self._load_config()
            position = config.get(self.POSITION_KEY)

            if position and isinstance(position, dict):
                # 验证必要字段
                required = ['x', 'y', 'width', 'height']
                if all(k in position for k in required):
                    return position
            return None
        except Exception:
            return None

    def _load_config(self) -> dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def validate_position(self, x: int, y: int, width: int, height: int,
                         screen_width: int = None, screen_height: int = None) -> dict:
        """
        验证位置是否在屏幕可见范围内

        Args:
            x: 窗口 X 坐标
            y: 窗口 Y 坐标
            width: 窗口宽度
            height: 窗口高度
            screen_width: 屏幕宽度（可选，自动检测）
            screen_height: 屏幕高度（可选，自动检测）

        Returns:
            {'valid': bool, 'x': int, 'y': int, 'width': int, 'height': int}
            如果无效，返回修正后的位置
        """
        # 获取屏幕尺寸
        if screen_width is None or screen_height is None:
            bounds = self.get_screen_bounds()
            screen_width = bounds.get('width', 1920)
            screen_height = bounds.get('height', 1080)

        result = {
            'valid': True,
            'x': x,
            'y': y,
            'width': width,
            'height': height
        }

        # 确保窗口尺寸合理
        result['width'] = max(self.MIN_VISIBLE_SIZE, min(width, screen_width))
        result['height'] = max(self.MIN_VISIBLE_SIZE, min(height, screen_height))

        # 检查窗口是否至少有 MIN_VISIBLE_SIZE 像素在屏幕内
        # 右边界检查
        if x + self.MIN_VISIBLE_SIZE > screen_width:
            result['x'] = screen_width - result['width']
            result['valid'] = False

        # 下边界检查
        if y + self.MIN_VISIBLE_SIZE > screen_height:
            result['y'] = screen_height - result['height']
            result['valid'] = False

        # 左边界检查
        if x + result['width'] < self.MIN_VISIBLE_SIZE:
            result['x'] = 0
            result['valid'] = False

        # 上边界检查
        if y + result['height'] < self.MIN_VISIBLE_SIZE:
            result['y'] = 0
            result['valid'] = False

        # 确保坐标不为负（除非多显示器）
        if result['x'] < -screen_width:
            result['x'] = 0
            result['valid'] = False

        if result['y'] < -screen_height:
            result['y'] = 0
            result['valid'] = False

        return result

    def get_screen_bounds(self) -> dict:
        """
        获取屏幕边界

        Returns:
            {'width': int, 'height': int}
        """
        try:
            # 尝试使用 tkinter 获取屏幕尺寸
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
            return {'width': width, 'height': height}
        except Exception:
            pass

        try:
            # Windows 平台使用 ctypes
            if sys.platform == 'win32':
                import ctypes
                user32 = ctypes.windll.user32
                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)
                return {'width': width, 'height': height}
        except Exception:
            pass

        # 默认值
        return {'width': 1920, 'height': 1080}

    def get_default_position(self, width: int = 1200, height: int = 800) -> dict:
        """
        获取默认窗口位置（屏幕居中）

        Args:
            width: 窗口宽度
            height: 窗口高度

        Returns:
            {'x': int, 'y': int, 'width': int, 'height': int}
        """
        bounds = self.get_screen_bounds()
        screen_width = bounds['width']
        screen_height = bounds['height']

        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        return {
            'x': max(0, x),
            'y': max(0, y),
            'width': width,
            'height': height
        }

    def get_restored_position(self, default_width: int = 1200, default_height: int = 800) -> dict:
        """
        获取恢复的窗口位置（如果保存的位置无效则返回默认位置）

        Args:
            default_width: 默认窗口宽度
            default_height: 默认窗口高度

        Returns:
            {'x': int, 'y': int, 'width': int, 'height': int, 'maximized': bool}
        """
        saved = self.load_position()

        if saved:
            validated = self.validate_position(
                saved['x'], saved['y'],
                saved['width'], saved['height']
            )

            if validated['valid']:
                return {
                    'x': saved['x'],
                    'y': saved['y'],
                    'width': saved['width'],
                    'height': saved['height'],
                    'maximized': saved.get('maximized', False)
                }
            else:
                # 使用修正后的位置
                return {
                    'x': validated['x'],
                    'y': validated['y'],
                    'width': validated['width'],
                    'height': validated['height'],
                    'maximized': False
                }

        # 返回默认位置
        default = self.get_default_position(default_width, default_height)
        default['maximized'] = False
        return default

