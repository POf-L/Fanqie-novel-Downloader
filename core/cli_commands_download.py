# -*- coding: utf-8 -*-
"""
CLI 子命令实现（搜索/信息/下载/批量）- 从 core/cli.py 拆分
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from core.cli_utils import format_table
from utils.platform_utils import detect_platform, get_feature_status_report

def cmd_search(args):
    """搜索书籍命令"""
    from core.novel_downloader import get_api_manager
    from config.config import CONFIG
    
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
    from core.novel_downloader import get_api_manager
    
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
    from core.novel_downloader import downloader_instance
    from utils.platform_utils import detect_platform
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
        # 默认保存到程序目录下的novels文件夹
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        save_path = os.path.join(base_dir, 'novels')
    
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
    success = downloader_instance.run_download(
        book_id=book_id,
        save_path=save_path,
        file_format=file_format,
        gui_callback=progress_callback,
    )
    
    if success:
        print("\n下载完成!")
        return 0
    else:
        print("\n下载失败")
        return 1


def cmd_batch_download(args):
    """批量下载书籍命令"""
    from core.novel_downloader import batch_downloader
    import os
    import time

    # 解析书籍ID列表
    book_ids = []
    if args.book_ids:
        # 从命令行参数获取
        for book_id in args.book_ids:
            # 从 URL 提取 ID
            if 'fanqienovel.com' in book_id:
                import re
                match = re.search(r'/page/(\d+)', book_id)
                if match:
                    book_id = match.group(1)

            if book_id.isdigit():
                book_ids.append(book_id)
            else:
                print(f"警告: 跳过无效的书籍ID: {book_id}")

    if args.file:
        # 从文件读取书籍ID列表
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # 支持 ID 或 URL 格式
                        if 'fanqienovel.com' in line:
                            import re
                            match = re.search(r'/page/(\d+)', line)
                            if match:
                                book_ids.append(match.group(1))
                        elif line.isdigit():
                            book_ids.append(line)
        except FileNotFoundError:
            print(f"错误: 文件不存在: {args.file}")
            return 1
        except Exception as e:
            print(f"错误: 读取文件失败: {e}")
            return 1

    if not book_ids:
        print("错误: 请提供至少一个书籍ID")
        return 1

    # 确定保存路径
    save_path = args.path
    if not save_path:
        # 默认保存到程序目录下的novels文件夹
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        save_path = os.path.join(base_dir, 'novels')

    # 确保目录存在
    os.makedirs(save_path, exist_ok=True)

    # 确定格式
    file_format = args.format or 'txt'
    if file_format not in ['txt', 'epub']:
        print(f"警告: 不支持的格式 '{file_format}'，使用默认格式 txt")
        file_format = 'txt'

    # 并发设置
    max_concurrent = min(args.concurrent or 3, 5)  # 最大5个并发

    print(f"开始批量下载 {len(book_ids)} 本书籍")
    print(f"保存路径: {save_path}")
    print(f"文件格式: {file_format}")
    print(f"并发数量: {max_concurrent}")
    print("-" * 50)

    # 使用统一的批量下载核心（core.novel_downloader.BatchDownloader）
    start_time = time.time()

    def batch_progress_callback(current, total, book_name, status, message):
        """批量下载进度回调 (current=书籍序号，从1开始)"""
        try:
            book_id = book_ids[current - 1] if 1 <= current <= len(book_ids) else ""
        except Exception:
            book_id = ""

        prefix = f"[{current}/{total}]"

        if status == 'success':
            print(f"{prefix} ✓ 下载完成: {book_id} - {book_name}")
        elif status == 'failed':
            print(f"{prefix} ✗ 下载失败: {book_id} - {book_name} - {message}")
        else:
            # downloading / 其他状态
            if book_id:
                print(f"{prefix} {book_id} - {message}")
            else:
                print(f"{prefix} {message}")

    batch_result = batch_downloader.run_batch(
        book_ids=book_ids,
        save_path=save_path,
        file_format=file_format,
        progress_callback=batch_progress_callback,
        delay_between_books=0.0,
        max_concurrent=max_concurrent,
    )

    # 显示批量下载结果
    end_time = time.time()
    duration = end_time - start_time

    successful_downloads = int(batch_result.get('success_count', 0) or 0)
    failed_downloads = int(batch_result.get('failed_count', 0) or 0)
    download_results_list = batch_result.get('results', []) or []

    print("\n" + "=" * 60)
    print("批量下载完成!")
    print(f"总计: {len(book_ids)} 本书籍")
    print(f"成功: {successful_downloads} 本")
    print(f"失败: {failed_downloads} 本")
    print(f"用时: {duration:.1f} 秒")

    # 显示详细结果
    if download_results_list:
        print("\n详细结果:")
        headers = ['序号', '书籍ID', '状态', '时间']
        rows = []
        for r in download_results_list:
            book_id = r.get('book_id', '')
            ok = bool(r.get('success'))
            status = "✓ 成功" if ok else "✗ 失败"
            msg = str(r.get('message', '') or '')
            if msg and not ok:
                status += f" ({msg[:30]}...)" if len(msg) > 30 else f" ({msg})"

            rows.append([
                int(r.get('index', 0) or 0),
                book_id,
                status,
                r.get('timestamp', '')
            ])

        # 按序号排序
        rows.sort(key=lambda x: x[0])
        print(format_table(headers, rows))

    # Git提交功能
    if args.commit and successful_downloads > 0:
        print("\n" + "-" * 50)
        print("正在执行Git提交...")

        try:
            # 检查是否在Git仓库中
            result = subprocess.run(['git', 'rev-parse', '--git-dir'],
                                  capture_output=True, text=True, cwd=save_path)
            if result.returncode != 0:
                print("警告: 当前目录不是Git仓库，跳过提交")
            else:
                # 添加所有新文件
                subprocess.run(['git', 'add', '.'], cwd=save_path, check=True)

                # 创建提交信息
                commit_msg = f"批量下载完成: {successful_downloads}本书籍 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                if failed_downloads > 0:
                    commit_msg += f" (失败: {failed_downloads}本)"

                # 执行提交
                result = subprocess.run(['git', 'commit', '-m', commit_msg],
                                      capture_output=True, text=True, cwd=save_path)

                if result.returncode == 0:
                    print(f"✓ Git提交成功: {commit_msg}")
                else:
                    print(f"Git提交失败: {result.stderr}")

        except subprocess.CalledProcessError as e:
            print(f"Git操作失败: {e}")
        except FileNotFoundError:
            print("警告: 未找到Git命令，请确保Git已安装")

    print("=" * 60)

    # 返回状态码
    return 0 if failed_downloads == 0 else 1
