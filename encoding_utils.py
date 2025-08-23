#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
编码工具模块
提供跨平台的UTF-8编码支持，确保在不同环境下正确处理中文字符
"""

import sys
import os
import locale
import io

def setup_utf8_encoding():
    """
    设置UTF-8编码环境
    在Windows和其他平台上确保正确的UTF-8编码处理
    """
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'
    
    # 设置locale
    if sys.platform.startswith('win'):
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_ALL, 'Chinese (Simplified)_China.UTF-8')
                except locale.Error:
                    pass  # 使用默认编码
    else:
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            except locale.Error:
                pass  # 使用默认编码

def safe_print(*args, **kwargs):
    """
    安全的print函数，确保在所有环境下正确输出UTF-8字符
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 如果直接print失败，尝试编码为UTF-8
        try:
            encoded_args = []
            for arg in args:
                if isinstance(arg, str):
                    encoded_args.append(arg.encode('utf-8', errors='replace').decode('utf-8'))
                else:
                    encoded_args.append(str(arg))
            print(*encoded_args, **kwargs)
        except Exception:
            # 最后的fallback，移除非ASCII字符
            ascii_args = []
            for arg in args:
                if isinstance(arg, str):
                    ascii_args.append(arg.encode('ascii', errors='replace').decode('ascii'))
                else:
                    ascii_args.append(str(arg).encode('ascii', errors='replace').decode('ascii'))
            print(*ascii_args, **kwargs)

def get_safe_encoding():
    """
    获取安全的编码方式
    """
    if sys.platform.startswith('win'):
        return 'utf-8'
    else:
        return 'utf-8'

def ensure_utf8_output():
    """
    确保标准输出使用UTF-8编码
    """
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    else:
        # Python 3.6及以下版本的兼容性处理
        try:
            if sys.stdout.encoding != 'utf-8':
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            if sys.stderr.encoding != 'utf-8':
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass

# 模块导入时自动设置编码
setup_utf8_encoding()
ensure_utf8_output() 