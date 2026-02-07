# -*- coding: utf-8 -*-
"""运行时初始化工具：统一路径、打包修复和编码设置。"""

import os
import sys
from typing import Callable, Optional


def get_runtime_base_path() -> str:
    """获取当前运行环境基础路径（开发/打包统一）。"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_runtime_path() -> str:
    """确保基础路径已加入 sys.path，并返回该路径。"""
    base_path = get_runtime_base_path()
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    return base_path


def apply_packaging_fixes(debug_log: Optional[Callable[[str], None]] = None) -> bool:
    """应用打包兼容修复。"""
    try:
        from utils.packaging_fixes import apply_all_fixes
        apply_all_fixes()
        if debug_log:
            debug_log("packaging_fixes 加载成功")
        return True
    except ImportError as exc:
        if debug_log:
            debug_log(f"packaging_fixes 导入失败: {exc}")
    except Exception as exc:
        if debug_log:
            debug_log(f"packaging_fixes 执行失败: {exc}")
    return False


def apply_encoding_fixes(debug_log: Optional[Callable[[str], None]] = None):
    """应用编码兼容修复并返回 safe_print（如果可用）。"""
    try:
        from utils.encoding_utils import setup_utf8_encoding, patch_print, safe_print
        setup_utf8_encoding()
        patch_print()
        if debug_log:
            debug_log("encoding_utils 加载成功")
        return safe_print
    except ImportError as exc:
        if debug_log:
            debug_log(f"encoding_utils 导入失败: {exc}")
    except Exception as exc:
        if debug_log:
            debug_log(f"encoding_utils 执行失败: {exc}")

    # 备用编码设置方案
    if sys.platform == 'win32':
        try:
            os.system('chcp 65001 >nul 2>&1')
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            
            # 尝试直接修复 stdout/stderr
            import io
            try:
                if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer:
                    sys.stdout = io.TextIOWrapper(
                        sys.stdout.buffer,
                        encoding='utf-8',
                        errors='replace',
                        line_buffering=True
                    )
            except:
                pass
                
            try:
                if hasattr(sys.stderr, 'buffer') and sys.stderr.buffer:
                    sys.stderr = io.TextIOWrapper(
                        sys.stderr.buffer,
                        encoding='utf-8',
                        errors='replace',
                        line_buffering=True
                    )
            except:
                pass
                
            if debug_log:
                debug_log("备用编码设置已应用")
        except Exception as exc:
            if debug_log:
                debug_log(f"备用编码设置失败: {exc}")
    return None


def get_web_resource_paths(web_file_path: str):
    """获取 web 模块模板与静态目录，兼容开发/打包环境。"""
    base_path = get_runtime_base_path()
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(base_path, 'templates')
        static_folder = os.path.join(base_path, 'static')
    else:
        module_dir = os.path.dirname(web_file_path)
        template_folder = os.path.join(module_dir, 'templates')
        static_folder = os.path.join(module_dir, 'static')
    return template_folder, static_folder
