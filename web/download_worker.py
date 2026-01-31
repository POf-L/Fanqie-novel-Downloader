# -*- coding: utf-8 -*-
"""
下载工作线程 - 后台下载任务执行
"""

import os
import sys
import time
import threading
import queue
import re
import requests
from datetime import datetime

# 添加父目录到路径
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        _base_path = sys._MEIPASS
    else:
        _base_path = os.path.dirname(sys.executable)
    if _base_path not in sys.path:
        sys.path.insert(0, _base_path)
else:
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

from config.config import CONFIG, print_lock
from core.novel_downloader import Run
from .download_history import get_download_history_manager
from .task_manager import task_manager


# 全局变量
download_queue = queue.Queue()
current_download_status = {
    'is_downloading': False,
    'progress': 0,
    'message': '',
    'book_name': '',
    'total_chapters': 0,
    'downloaded_chapters': 0,
    'queue_total': 0,
    'queue_done': 0,
    'queue_current': 0,
    'messages': []
}
status_lock = threading.Lock()


def get_status():
    """获取当前下载状态"""
    with status_lock:
        status = current_download_status.copy()
        status['messages'] = current_download_status['messages'].copy()
        current_download_status['messages'] = []
        return status


def update_status(progress=None, message=None, **kwargs):
    """更新下载状态"""
    with status_lock:
        if progress is not None:
            current_download_status['progress'] = progress
        if message is not None:
            current_download_status['message'] = message
            current_download_status['messages'].append(message)
            if len(current_download_status['messages']) > 100:
                current_download_status['messages'] = current_download_status['messages'][-50:]
        for key, value in kwargs.items():
            if key in current_download_status:
                current_download_status[key] = value


def download_worker():
    """后台下载工作线程"""
    api = None
    api_manager = None
    
    while True:
        try:
            task = download_queue.get(timeout=1)
            if task is None:
                continue
            
            book_id = task.get('book_id')
            save_path = task.get('save_path', os.getcwd())
            file_format = task.get('file_format', 'txt')
            start_chapter = task.get('start_chapter', None)
            end_chapter = task.get('end_chapter', None)
            selected_chapters = task.get('selected_chapters', None)

            # 如果是队列任务，更新当前序号
            queue_current = 0
            with status_lock:
                queue_total = int(current_download_status.get('queue_total', 0) or 0)
                queue_done = int(current_download_status.get('queue_done', 0) or 0)
                if queue_total > 0:
                    queue_current = min(queue_done + 1, queue_total)
                    current_download_status['queue_current'] = queue_current

            update_status(is_downloading=True, progress=0, message='初始化中...')
            
            # 初始化API管理器
            if not api_manager:
                from core.api_manager import get_api_manager
                api_manager = get_api_manager()
                if api_manager:
                    api = api_manager
            
            if not api:
                update_status(message='API 未初始化', progress=0, is_downloading=False)
                continue
            
            try:
                # 设置进度回调
                def progress_callback(progress, message):
                    if progress >= 0:
                        update_status(progress=progress, message=message)
                    else:
                        update_status(message=message)
                
                # 获取书籍信息
                update_status(message='正在连接书籍...')
                
                # 增加超时重试机制
                book_detail = None
                for _ in range(3):
                    book_detail = api_manager.get_book_detail(book_id)
                    if book_detail:
                        break
                    time.sleep(1)
                
                if not book_detail:
                    update_status(message='获取书籍信息失败，请检查书籍是否已下架', is_downloading=False)
                    continue
                
                # 检查是否有错误（如书籍下架）
                if isinstance(book_detail, dict) and book_detail.get('_error'):
                    error_type = book_detail.get('_error')
                    if error_type == 'BOOK_REMOVE':
                        update_status(message='该书籍已下架，无法下载', is_downloading=False)
                    else:
                        update_status(message=f'获取书籍信息失败: {error_type}', is_downloading=False)
                    continue
                
                book_name = book_detail.get('book_name', book_id)
                update_status(book_name=book_name, message=f'正在准备下载: {book_name}')
                
                # 执行下载
                update_status(message='正在启动下载引擎...')
                success = Run(book_id, save_path, file_format, start_chapter, end_chapter, selected_chapters, progress_callback)

                # 更新队列进度
                has_more = False
                queue_total = 0
                queue_done = 0
                with status_lock:
                    queue_total = int(current_download_status.get('queue_total', 0) or 0)
                    if queue_total > 0:
                        queue_done = int(current_download_status.get('queue_done', 0) or 0)
                        queue_done = min(queue_done + 1, queue_total)
                        current_download_status['queue_done'] = queue_done
                        has_more = queue_done < queue_total

                if success:
                    # 记录下载历史
                    try:
                        history_manager = get_download_history_manager()
                        # 构建保存路径
                        from core.file_utils import sanitize_filename, generate_filename
                        safe_book_name = sanitize_filename(book_name)
                        author_name = book_detail.get('author', '')
                        output_filename = generate_filename(safe_book_name, author_name, file_format)
                        full_save_path = os.path.join(save_path, output_filename)
                        
                        history_manager.add_record(
                            book_id=book_id,
                            book_name=book_name,
                            author=author_name,
                            save_path=full_save_path,
                            file_format=file_format,
                            chapter_count=book_detail.get('serial_count', 0)
                        )
                    except Exception as hist_err:
                        print(f"记录下载历史失败: {hist_err}")
                    
                    if has_more:
                        update_status(
                            progress=0,
                            message=f'正在下载第 {queue_done + 1}/{queue_total} 本书籍',
                            is_downloading=True,
                            queue_current=min(queue_done + 1, queue_total)
                        )
                    else:
                        if queue_total > 0:
                            update_status(
                                progress=100,
                                message=f'队列完成！共 {queue_total} 本书已保存到: {save_path}',
                                is_downloading=False,
                                queue_total=0,
                                queue_done=0,
                                queue_current=0
                            )
                        else:
                            update_status(progress=100, message=f'下载成功！已保存到: {save_path}', is_downloading=False)
                else:
                    if has_more:
                        update_status(
                            progress=0,
                            message=f'下载失败 ({queue_done + 1}/{queue_total})，继续下一本...',
                            is_downloading=True,
                            queue_current=min(queue_done + 1, queue_total)
                        )
                    else:
                        if queue_total > 0:
                            update_status(
                                progress=0,
                                message=f'队列完成，部分失败。已保存到: {save_path}',
                                is_downloading=False,
                                queue_total=0,
                                queue_done=0,
                                queue_current=0
                            )
                        else:
                            update_status(message='下载已中断', progress=0, is_downloading=False)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_str = str(e)
                update_status(message=f'下载异常: {error_str}', progress=0, is_downloading=False)
                print(f"下载异常: {error_str}")
        
        except queue.Empty:
            continue
        except Exception as e:
            error_str = str(e)
            update_status(message=f'工作线程异常: {error_str}', progress=0, is_downloading=False)
            print(f"工作线程异常: {error_str}")


# 启动后台下载线程
download_thread = threading.Thread(target=download_worker, daemon=True)
download_thread.start()
