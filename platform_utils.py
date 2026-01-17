# -*- coding: utf-8 -*-
"""
平台检测工具模块 - 检测运行环境并提供平台适配配置
"""

import os
import sys
import platform
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class PlatformInfo:
    """平台信息数据类"""
    os_name: str                          # 'windows', 'linux', 'darwin', 'termux'
    os_version: str                       # 操作系统版本
    desktop_env: str                      # 桌面环境 (Linux only)
    is_gui_available: bool                # GUI 是否可用
    is_termux: bool                       # 是否在 Termux 环境
    available_features: List[str] = field(default_factory=list)  # 可用功能列表


# 已知在无边框模式下有问题的窗口管理器
PROBLEMATIC_WINDOW_MANAGERS = [
    'i3', 'i3wm', 'sway', 'bspwm', 'dwm', 'awesome', 
    'xmonad', 'qtile', 'herbstluftwm', 'openbox', 'fluxbox'
]

# 所有可能的功能列表
ALL_FEATURES = [
    'gui_webview',      # PyWebView GUI
    'gui_browser',      # 浏览器回退模式
    'folder_dialog',    # 文件夹选择对话框
    'cli_mode',         # 命令行模式
    'auto_update',      # 自动更新
    'frameless_window', # 无边框窗口
]


def _detect_termux() -> bool:
    """检测是否在 Termux 环境中运行"""
    # Termux 设置 PREFIX 环境变量指向 /data/data/com.termux/files/usr
    prefix = os.environ.get('PREFIX', '')
    return 'com.termux' in prefix or '/data/data/com.termux' in prefix


def _detect_desktop_environment() -> str:
    """检测 Linux 桌面环境"""
    if sys.platform != 'linux':
        return ''
    
    # 检查常见的桌面环境变量
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    if desktop:
        return desktop
    
    desktop_session = os.environ.get('DESKTOP_SESSION', '').lower()
    if desktop_session:
        return desktop_session
    
    # 检查窗口管理器
    wm = os.environ.get('XDG_SESSION_TYPE', '').lower()
    if wm:
        return wm
    
    return 'unknown'


def _get_os_name() -> str:
    """获取标准化的操作系统名称"""
    if _detect_termux():
        return 'termux'
    
    plat = sys.platform
    if plat == 'win32':
        return 'windows'
    elif plat == 'darwin':
        return 'darwin'
    elif plat.startswith('linux'):
        return 'linux'
    else:
        return plat


def _get_os_version() -> str:
    """获取操作系统版本"""
    try:
        return platform.version()
    except Exception:
        return 'unknown'


def check_gui_dependencies() -> Tuple[bool, List[str]]:
    """
    检查 GUI 依赖是否可用
    
    Returns:
        (is_available, missing_dependencies): 可用性和缺失依赖列表
    """
    missing = []
    
    # 检查 PyWebView
    try:
        import webview
        _ = webview
    except ImportError:
        missing.append('pywebview')
    
    # 注意: tkinter 检查已移除，文件夹选择改为前端实现
    
    is_available = len(missing) == 0
    return is_available, missing


def is_frameless_supported() -> bool:
    """
    检测当前环境是否支持无边框窗口
    
    Returns:
        bool: 是否支持无边框窗口
    """
    os_name = _get_os_name()
    
    # Windows 和 macOS 通常支持无边框
    if os_name in ('windows', 'darwin'):
        return True
    
    # Termux 不支持 GUI
    if os_name == 'termux':
        return False
    
    # Linux 需要检查桌面环境
    if os_name == 'linux':
        desktop = _detect_desktop_environment()
        
        # 检查是否是有问题的窗口管理器
        for wm in PROBLEMATIC_WINDOW_MANAGERS:
            if wm in desktop:
                return False
        
        # Wayland 下无边框可能有问题
        session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        if session_type == 'wayland':
            # 某些 Wayland 合成器支持，但保守起见返回 False
            return False
        
        return True
    
    return False


def get_window_config() -> dict:
    """
    获取平台适配的窗口配置
    
    Returns:
        dict: PyWebView 窗口配置参数
    """
    config = {
        'title': '番茄小说下载器',
        'width': 1200,
        'height': 800,
        'min_size': (1000, 700),
        'background_color': '#0a0a0a',
        'frameless': False,  # 默认使用有边框
    }
    
    if is_frameless_supported():
        config['frameless'] = True
    
    return config


def _get_available_features() -> List[str]:
    """获取当前平台可用的功能列表"""
    features = []
    os_name = _get_os_name()
    
    # CLI 模式在所有平台都可用
    features.append('cli_mode')
    
    # Termux 只支持 CLI
    if os_name == 'termux':
        return features
    
    # 检查 GUI 依赖
    gui_available, _ = check_gui_dependencies()
    
    if gui_available:
        features.append('gui_webview')
        if is_frameless_supported():
            features.append('frameless_window')
    
    # 浏览器回退模式在有网络的环境都可用
    features.append('gui_browser')
    
    # 文件夹选择现在通过前端实现，始终可用
    features.append('folder_dialog')
    
    # 自动更新仅在打包后的程序中可用
    if getattr(sys, 'frozen', False) and os_name != 'termux':
        features.append('auto_update')
    
    return features


def detect_platform() -> PlatformInfo:
    """
    检测当前平台信息
    
    Returns:
        PlatformInfo: 平台信息对象
    """
    os_name = _get_os_name()
    os_version = _get_os_version()
    desktop_env = _detect_desktop_environment() if os_name == 'linux' else ''
    is_termux = _detect_termux()
    gui_available, _ = check_gui_dependencies()
    available_features = _get_available_features()
    
    # Termux 环境下 GUI 不可用
    if is_termux:
        gui_available = False
    
    return PlatformInfo(
        os_name=os_name,
        os_version=os_version,
        desktop_env=desktop_env,
        is_gui_available=gui_available,
        is_termux=is_termux,
        available_features=available_features
    )


def get_feature_status_report() -> str:
    """
    获取功能可用性报告
    
    Returns:
        str: 格式化的功能状态报告
    """
    info = detect_platform()
    
    lines = [
        f"平台: {info.os_name} ({info.os_version})",
    ]
    
    if info.desktop_env:
        lines.append(f"桌面环境: {info.desktop_env}")
    
    if info.is_termux:
        lines.append("运行环境: Termux (Android)")
    
    lines.append("")
    lines.append("功能状态:")
    
    feature_names = {
        'gui_webview': 'PyWebView GUI',
        'gui_browser': '浏览器模式',
        'folder_dialog': '文件夹选择对话框',
        'cli_mode': '命令行模式',
        'auto_update': '自动更新',
        'frameless_window': '无边框窗口',
    }
    
    for feature_id, feature_name in feature_names.items():
        status = 'Y' if feature_id in info.available_features else 'N'
        lines.append(f"  [{status}] {feature_name}")
    
    return '\n'.join(lines)


def is_feature_available(feature: str) -> bool:
    """
    检查指定功能是否可用
    
    Args:
        feature: 功能标识符
    
    Returns:
        bool: 功能是否可用
    """
    info = detect_platform()
    return feature in info.available_features


def get_unavailable_feature_message(feature: str) -> str:
    """
    获取功能不可用的说明消息
    
    Args:
        feature: 功能标识符
    
    Returns:
        str: 说明消息
    """
    messages = {
        'gui_webview': '当前环境不支持 PyWebView GUI，请安装 pywebview 或使用浏览器模式',
        'gui_browser': '浏览器模式不可用',
        'folder_dialog': '文件夹选择对话框不可用，请手动输入路径。可安装 tkinter 启用此功能',
        'cli_mode': '命令行模式不可用',
        'auto_update': '自动更新仅在打包后的程序中可用，请从 GitHub Releases 手动下载更新',
        'frameless_window': '当前桌面环境不支持无边框窗口，将使用标准窗口边框',
    }
    return messages.get(feature, f'功能 {feature} 不可用')


# ===================== 窗口位置管理器 =====================

import json

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
            config_dir: 配置文件存储目录，默认为用户目录
        """
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = os.path.expanduser('~')
        
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
