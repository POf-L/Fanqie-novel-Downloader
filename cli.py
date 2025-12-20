# -*- coding: utf-8 -*-
"""
命令行界面入口 - 支持 Termux 和无 GUI 环境
"""

import argparse
import sys
import os
from typing import Optional

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from platform_utils import detect_platform, get_feature_status_report
from locales import t


def format_table(headers: list, rows: list, col_widths: Optional[list] = None) -> str:
    """
    格式化文本表格
    
    Args:
        headers: 表头列表
        rows: 数据行列表
        col_widths: 列宽列表（可选）
    
    Returns:
        格式化的表格字符串
    """
    if not rows:
        return "无数据"
    
    # 计算列宽
    if col_widths is None:
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(str(header))
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(min(max_width, 40))  # 最大宽度 40
    
    # 格式化表头
    header_line = " | ".join(
        str(h).ljust(col_widths[i])[:col_widths[i]] 
        for i, h in enumerate(headers)
    )
    separator = "-+-".join("-" * w for w in col_widths)
    
    # 格式化数据行
    data_lines = []
    for row in rows:
        line = " | ".join(
            str(row[i] if i < len(row) else "").ljust(col_widths[i])[:col_widths[i]]
            for i in range(len(headers))
        )
        data_lines.append(line)
    
    return "\n".join([header_line, separator] + data_lines)


def cmd_search(args):
    """搜索书籍命令"""
    from novel_downloader import get_api_manager
    from config import CONFIG
    
    keyword = args.keyword
    if not keyword:
        print("错误: 请提供搜索关键词")
        return 1
    
    print(f"正在搜索: {keyword}")
    
    api = get_api_manager()
    result = api.search_books(keyword, offset=0)
    
    if not result or not result.get('data'):
        print("未找到相关书籍")
        return 0
    
    # 解析搜索结果
    search_data = result.get('data', {})
    books = []
    
    search_tabs = search_data.get('search_tabs', [])
    for tab in search_tabs:
        if tab.get('tab_type') == 3:
            tab_data = tab.get('data', [])
            for item in tab_data:
                book_data_list = item.get('book_data', [])
                for book in book_data_list:
                    if isinstance(book, dict):
                        status_code = str(book.get('creation_status', ''))
                        if status_code == '0':
                            status = '已完结'
                        elif status_code == '1':
                            status = '连载中'
                        else:
                            status = ''
                        
                        books.append([
                            book.get('book_id', ''),
                            book.get('book_name', '未知')[:20],
                            book.get('author', '未知')[:10],
                            status
                        ])
            break
    
    if not books:
        print("未找到相关书籍")
        return 0
    
    # 显示结果表格
    headers = ['书籍ID', '书名', '作者', '状态']
    print(f"\n找到 {len(books)} 本书籍:\n")
    print(format_table(headers, books))
    
    return 0


def cmd_info(args):
    """显示书籍信息命令"""
    from novel_downloader import get_api_manager
    
    book_id = args.book_id
    if not book_id:
        print("错误: 请提供书籍ID")
        return 1
    
    # 从 URL 提取 ID
    if 'fanqienovel.com' in book_id:
        import re
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
    
    if not book_id.isdigit():
        print("错误: 书籍ID必须是数字")
        return 1
    
    print(f"正在获取书籍信息: {book_id}")
    
    api = get_api_manager()
    
    # 获取书籍详情
    book_detail = api.get_book_detail(book_id)
    if not book_detail:
        print("错误: 无法获取书籍信息")
        return 1
    
    # 获取章节列表
    chapters_data = api.get_chapter_list(book_id)
    chapter_count = 0
    if chapters_data:
        if isinstance(chapters_data, dict):
            all_ids = chapters_data.get("allItemIds", [])
            chapter_count = len(all_ids)
        elif isinstance(chapters_data, list):
            chapter_count = len(chapters_data)
    
    # 显示信息
    print("\n" + "=" * 50)
    print(f"书名: {book_detail.get('book_name', '未知')}")
    print(f"作者: {book_detail.get('author', '未知')}")
    print(f"章节数: {chapter_count}")
    print("-" * 50)
    
    abstract = book_detail.get('abstract', '')
    if abstract:
        print("简介:")
        # 限制简介长度
        if len(abstract) > 200:
            abstract = abstract[:200] + "..."
        print(abstract)
    
    print("=" * 50)
    
    return 0


def cmd_download(args):
    """下载书籍命令"""
    from novel_downloader import Run
    from platform_utils import detect_platform
    import os
    
    book_id = args.book_id
    if not book_id:
        print("错误: 请提供书籍ID")
        return 1
    
    # 从 URL 提取 ID
    if 'fanqienovel.com' in book_id:
        import re
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
    
    if not book_id.isdigit():
        print("错误: 书籍ID必须是数字")
        return 1
    
    # 确定保存路径
    save_path = args.path
    if not save_path:
        # 默认保存到用户下载目录
        home = os.path.expanduser('~')
        save_path = os.path.join(home, 'Downloads')
        if not os.path.exists(save_path):
            save_path = home
    
    # 确保目录存在
    os.makedirs(save_path, exist_ok=True)
    
    # 确定格式
    file_format = args.format or 'txt'
    if file_format not in ['txt', 'epub']:
        print(f"警告: 不支持的格式 '{file_format}'，使用默认格式 txt")
        file_format = 'txt'
    
    print(f"开始下载书籍: {book_id}")
    print(f"保存路径: {save_path}")
    print(f"文件格式: {file_format}")
    print("-" * 50)
    
    # 进度回调
    def progress_callback(progress, message):
        if progress >= 0:
            print(f"[{progress:3d}%] {message}")
        else:
            print(f"       {message}")
    
    # 执行下载
    success = Run(
        book_id=book_id,
        save_path=save_path,
        file_format=file_format,
        gui_callback=progress_callback
    )
    
    if success:
        print("\n下载完成!")
        return 0
    else:
        print("\n下载失败")
        return 1


def cmd_status(args):
    """显示平台状态命令"""
    report = get_feature_status_report()
    print(report)
    return 0


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='fanqie-cli',
        description='番茄小说下载器 - 命令行版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s search "斗破苍穹"          搜索书籍
  %(prog)s info 12345                 查看书籍信息
  %(prog)s download 12345             下载书籍
  %(prog)s download 12345 -f epub     下载为 EPUB 格式
  %(prog)s status                     显示平台状态
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
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='显示平台状态')
    status_parser.set_defaults(func=cmd_status)
    
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
