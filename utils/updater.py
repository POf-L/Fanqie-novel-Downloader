# -*- coding: utf-8 -*-

"""
自动更新检查模块 - 从GitHub检查新版本
支持多平台：Windows, Linux, macOS

该文件仅保留公共入口，具体实现拆分到：
- utils/updater_release.py
- utils/updater_apply.py
"""

from .updater_release import (
    check_and_notify,
    check_update,
    format_update_message,
    get_current_platform,
    get_latest_release,
    get_latest_release_cached,
    parse_release_assets,
    parse_version,
)

from .updater_apply import (
    apply_unix_update,
    apply_update,
    apply_windows_update,
    can_auto_update,
    get_update_exe_path,
)

__all__ = [
    'apply_unix_update',
    'apply_update',
    'apply_windows_update',
    'can_auto_update',
    'check_and_notify',
    'check_update',
    'format_update_message',
    'get_current_platform',
    'get_latest_release',
    'get_latest_release_cached',
    'get_update_exe_path',
    'parse_release_assets',
    'parse_version',
]
