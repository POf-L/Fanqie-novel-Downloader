# -*- coding: utf-8 -*-
"""
编码处理工具模块 - 一劳永逸解决所有编码问题
"""

import sys
import os
import io
from typing import Any


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
        except:
            pass

        # 设置环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'

        # 重新包装 stdout 和 stderr 为 UTF-8
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                newline=None,
                line_buffering=True
            )

        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                newline=None,
                line_buffering=True
            )


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
            # 确保字符串可以安全编码
            return obj.encode('utf-8', errors='replace').decode('utf-8')
        else:
            # 转换为字符串后安全处理
            str_obj = str(obj)
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
        print(*safe_args, **kwargs)
    except Exception as e:
        # 如果还是失败，使用最基本的错误处理
        try:
            print(f"<print error: {e}>", **kwargs)
        except:
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