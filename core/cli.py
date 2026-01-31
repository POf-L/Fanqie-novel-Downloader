# -*- coding: utf-8 -*-
"""
命令行界面入口 - 支持 Termux 和无 GUI 环境
"""

import sys
import os

# 添加父目录到路径以便导入其他模块（打包环境和开发环境都需要）
if getattr(sys, 'frozen', False):
    # 打包环境
    if hasattr(sys, '_MEIPASS'):
        _base_path = sys._MEIPASS
    else:
        _base_path = os.path.dirname(sys.executable)
    if _base_path not in sys.path:
        sys.path.insert(0, _base_path)
else:
    # 开发环境
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

# 一劳永逸的编码处理 - 必须在所有其他导入之前
try:
    from utils.encoding_utils import setup_utf8_encoding, patch_print, safe_print
    # 设置全局UTF-8编码环境
    setup_utf8_encoding()
    # 替换print函数为编码安全版本
    patch_print()
    print = safe_print  # 确保当前模块使用安全版本
except ImportError:
    # 如果编码工具不存在，使用基本的编码设置
    if sys.platform == 'win32':
        try:
            os.system('chcp 65001 >nul 2>&1')
            os.environ['PYTHONIOENCODING'] = 'utf-8'
        except:
            pass

import argparse
from typing import Optional
import asyncio
import subprocess
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from utils.platform_utils import detect_platform, get_feature_status_report




from core.cli_commands_admin import cmd_api, cmd_config, cmd_status
from core.cli_commands_download import cmd_batch_download, cmd_download, cmd_info, cmd_search
def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='fanqie-cli',
        description='番茄小说下载器 - 命令行版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s search "斗破苍穹"                    搜索书籍
  %(prog)s info 12345                           查看书籍信息
  %(prog)s download 12345                       下载书籍
  %(prog)s download 12345 -f epub               下载为 EPUB 格式
  %(prog)s batch-download 12345 67890 --commit  批量下载并提交
  %(prog)s batch-download -i books.txt --commit 从文件批量下载
  %(prog)s status                               显示平台状态
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='显示详细输出')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索书籍')
    search_parser.add_argument('keyword', help='搜索关键词')
    search_parser.set_defaults(func=cmd_search)
    
    # info 命令
    info_parser = subparsers.add_parser('info', help='查看书籍信息')
    info_parser.add_argument('book_id', help='书籍ID或URL')
    info_parser.set_defaults(func=cmd_info)
    
    # download 命令
    download_parser = subparsers.add_parser('download', help='下载书籍')
    download_parser.add_argument('book_id', help='书籍ID或URL')
    download_parser.add_argument('-p', '--path', help='保存路径')
    download_parser.add_argument('-f', '--format', choices=['txt', 'epub'],
                                default='txt', help='输出格式 (默认: txt)')
    download_parser.set_defaults(func=cmd_download)

    # batch-download 命令
    batch_parser = subparsers.add_parser('batch-download', help='批量下载书籍')
    batch_parser.add_argument('book_ids', nargs='*', help='书籍ID或URL列表')
    batch_parser.add_argument('-i', '--file', help='包含书籍ID列表的文件路径')
    batch_parser.add_argument('-p', '--path', help='保存路径')
    batch_parser.add_argument('-f', '--format', choices=['txt', 'epub'],
                             default='txt', help='输出格式 (默认: txt)')
    batch_parser.add_argument('-c', '--concurrent', type=int, default=3,
                             help='并发下载数量 (默认: 3, 最大: 5)')
    batch_parser.add_argument('--commit', action='store_true',
                             help='下载完成后自动Git提交')
    batch_parser.set_defaults(func=cmd_batch_download)

    # status 命令
    status_parser = subparsers.add_parser('status', help='显示平台状态')
    status_parser.set_defaults(func=cmd_status)

    # config 命令
    config_parser = subparsers.add_parser('config', help='配置管理')
    config_parser.add_argument('action', choices=['list', 'set', 'get', 'reset'],
                               help='操作: list(列出所有配置), set(设置配置), get(获取配置), reset(重置配置)')
    config_parser.add_argument('key', nargs='?', help='配置键')
    config_parser.add_argument('value', nargs='?', help='配置值')
    config_parser.set_defaults(func=cmd_config)

    # api 命令
    api_parser = subparsers.add_parser('api', help='API 节点管理')
    api_parser.add_argument('action', choices=['list', 'select'],
                           help='操作: list(列出所有节点), select(选择节点)')
    api_parser.add_argument('mode', nargs='?', choices=['auto', 'manual'],
                           help='选择模式: auto(自动选择最快节点), manual(手动指定节点)')
    api_parser.add_argument('url', nargs='?', help='API 节点 URL (仅 manual 模式需要)')
    api_parser.set_defaults(func=cmd_api)

    return parser


def check_termux_dependencies():
    """检查 Termux 环境下的依赖"""
    platform_info = detect_platform()
    
    if platform_info.is_termux:
        # 检查是否缺少依赖
        missing = []
        try:
            import requests
        except ImportError:
            missing.append('requests')
        
        try:
            import aiohttp
        except ImportError:
            missing.append('aiohttp')
        
        if missing:
            print("=" * 50)
            print("Termux 环境检测到缺少依赖:")
            print(f"  缺少: {', '.join(missing)}")
            print("")
            print("建议使用 Termux 专用依赖文件安装:")
            print("  pip install -r requirements-termux.txt")
            print("=" * 50)
            print("")


def main():
    """CLI 主入口"""
    # 检测平台
    platform_info = detect_platform()
    
    # Termux 环境检查依赖
    check_termux_dependencies()
    
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    # 执行命令
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
