# -*- coding: utf-8 -*-
"""
编码处理工具模块 - 一劳永逸解决所有编码问题
"""

import sys
import os
import io
from typing import Any


# 保留原始 print，避免在 patch_print 后递归调用
_ORIGINAL_PRINT = print


def setup_utf8_encoding():
    """
    设置全局UTF-8编码环境
    一劳永逸解决所有编码问题
    """
    # Windows 控制台编码设置
    if sys.platform == 'win32':
        try:
            # 设置控制台代码页为 UTF-8
            os.system('chcp 65001 >nul 2>&1')
        except Exception:
            pass

        # 设置环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'

        # 尝试重新配置控制台模式（Windows 10+）
        try:
            import ctypes
            import ctypes.wintypes
            
            # 启用虚拟终端处理
            kernel32 = ctypes.windll.kernel32
            STD_OUTPUT_HANDLE = -11
            STD_ERROR_HANDLE = -12
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            
            for handle_id in [STD_OUTPUT_HANDLE, STD_ERROR_HANDLE]:
                handle = kernel32.GetStdHandle(handle_id)
                if handle:
                    mode = ctypes.wintypes.DWORD()
                    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
        except Exception:
            pass  # 忽略失败，继续其他设置

        # 重新包装 stdout 和 stderr 为 UTF-8
        # 注意：在打包环境中需要额外检查 buffer 是否可用
        try:
            if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer is not None:
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding='utf-8',
                    errors='replace',
                    newline=None,
                    line_buffering=True
                )
        except Exception:
            pass  # 打包环境可能没有 buffer，忽略

        try:
            if hasattr(sys.stderr, 'buffer') and sys.stderr.buffer is not None:
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer,
                    encoding='utf-8',
                    errors='replace',
                    newline=None,
                    line_buffering=True
                )
        except Exception:
            pass  # 打包环境可能没有 buffer，忽略
    
    # 非Windows系统也设置环境变量
    else:
        os.environ['PYTHONIOENCODING'] = 'utf-8'


def safe_str(obj: Any) -> str:
    """
    安全字符串转换，处理所有可能的编码问题

    Args:
        obj: 任意对象

    Returns:
        安全的字符串表示
    """
    try:
        if isinstance(obj, str):
            # 检查并替换Windows控制台不支持的Unicode字符
            result = obj
            # 常见的不支持字符替换
            char_replacements = {
                '✓': '[OK]',
                '❌': '[X]',
                '⚠': '[!]',
                '💡': '[i]',
                '✗': '[X]',
                '🎨': '[ART]',
                '⚠️': '[!]',
                '✅': '[OK]',
                '❎': '[X]'
            }
            
            for unicode_char, ascii_replacement in char_replacements.items():
                result = result.replace(unicode_char, ascii_replacement)
            
            # 确保字符串可以安全编码
            return result.encode('utf-8', errors='replace').decode('utf-8')
        else:
            # 转换为字符串后安全处理
            str_obj = str(obj)
            # 应用同样的字符替换
            for unicode_char, ascii_replacement in {'✓': '[OK]', '❌': '[X]', '⚠': '[!]', '💡': '[i]', '✗': '[X]', '🎨': '[ART]', '⚠️': '[!]', '✅': '[OK]', '❎': '[X]'}.items():
                str_obj = str_obj.replace(unicode_char, ascii_replacement)
            return str_obj.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return '<encoding error>'


def safe_print(*args, **kwargs):
    """
    编码安全的打印函数，替代内置 print

    Args:
        *args: 打印参数
        **kwargs: print 关键字参数
    """
    try:
        # 安全处理所有参数
        safe_args = [safe_str(arg) for arg in args]
        _ORIGINAL_PRINT(*safe_args, **kwargs)
    except UnicodeEncodeError as e:
        # 专门处理Unicode编码错误
        try:
            # 尝试使用ASCII兼容的输出
            ascii_args = []
            for arg in args:
                if isinstance(arg, str):
                    # 移除或替换所有非ASCII字符
                    ascii_str = ''.join(char if ord(char) < 128 else '?' for char in str(arg))
                    ascii_args.append(ascii_str)
                else:
                    ascii_args.append(str(arg))
            _ORIGINAL_PRINT(*ascii_args, **kwargs)
        except Exception:
            # 最后的备用方案
            try:
                _ORIGINAL_PRINT(f"<UnicodeEncodeError: {e}>", **kwargs)
            except Exception:
                pass
    except Exception as e:
        # 如果还是失败，使用最基本的错误处理
        try:
            _ORIGINAL_PRINT(f"<print error: {e}>", **kwargs)
        except Exception:
            pass


def patch_print():
    """
    替换内置的 print 函数为编码安全版本
    """
    import builtins
    builtins.print = safe_print


def safe_format(template: str, *args, **kwargs) -> str:
    """
    编码安全的字符串格式化

    Args:
        template: 格式化模板
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        安全格式化的字符串
    """
    try:
        # 安全处理所有参数
        safe_args = [safe_str(arg) for arg in args]
        safe_kwargs = {k: safe_str(v) for k, v in kwargs.items()}

        return template.format(*safe_args, **safe_kwargs)
    except Exception:
        return template + ' <format error>'


def get_safe_system_info() -> dict:
    """
    获取编码安全的系统信息

    Returns:
        系统信息字典
    """
    import platform

    try:
        return {
            'system': safe_str(platform.system()),
            'version': safe_str(platform.version()),
            'machine': safe_str(platform.machine()),
            'processor': safe_str(platform.processor()),
            'node': safe_str(platform.node()),
        }
    except Exception:
        return {
            'system': 'unknown',
            'version': 'unknown',
            'machine': 'unknown',
            'processor': 'unknown',
            'node': 'unknown',
        }


# 自动初始化（可选）
def auto_setup():
    """
    自动设置编码环境
    在模块导入时自动调用
    """
    setup_utf8_encoding()


# 如果需要自动初始化，取消下面的注释
# auto_setup()