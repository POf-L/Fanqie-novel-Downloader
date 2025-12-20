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
