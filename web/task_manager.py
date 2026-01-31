# -*- coding: utf-8 -*-
"""
任务管理器 - 管理下载队列和任务状态
"""

import os
import sys
import time
import threading
import json
from datetime import datetime
from typing import List, Dict, Optional


class TaskManager:
    """任务管理器 - 管理下载队列和任务状态"""
    
    def __init__(self):
        self._lock = None
        try:
            self._lock = threading.Lock()
        except ImportError:
            pass
        
        self.tasks = {}  # {task_id: task_info}
        self.current_task_id = None
        self.downloaded_chapters = {}  # {book_id: {index: content}}
    
    def add_task(self, task_id: str, book_id: str, book_name: str, 
                save_path: str, file_format: str = 'txt', 
                start_chapter=None, end_chapter=None, 
                selected_chapters=None):
        """添加任务到队列"""
        with self._lock:
            self.tasks[task_id] = {
                'task_id': task_id,
                'book_id': book_id,
                'book_name': book_name,
                'save_path': save_path,
                'file_format': file_format,
                'start_chapter': start_chapter,
                'end_chapter': end_chapter,
                'selected_chapters': selected_chapters,
                'status': 'pending',  # pending, downloading, completed, failed
                'progress': 0,
                'message': '等待中',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'started_at': None,
                'completed_at': None,
                'error': None
            }
        return True
    
    def update_task(self, task_id: str, **kwargs):
        """更新任务状态"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(kwargs)
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        with self._lock:
            return self.tasks.get(task_id)
    
    def get_current_task(self) -> Optional[Dict]:
        """获取当前正在执行的任务"""
        with self._lock:
            if self.current_task_id and self.current_task_id in self.tasks:
                return self.tasks[self.current_task_id]
        return None
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        with self._lock:
            tasks_list = list(self.tasks.values())
            return {
                'total': len(tasks_list),
                'pending': len([t for t in tasks_list if t['status'] == 'pending']),
                'downloading': len([t for t in tasks_list if t['status'] == 'downloading']),
                'completed': len([t for t in tasks_list if t['status'] == 'completed']),
                'failed': len([t for t in tasks_list if t['status'] == 'failed']),
                'current_task': self.get_current_task(),
                'tasks': tasks_list
            }
    
    def skip_current(self) -> bool:
        """跳过当前任务"""
        with self._lock:
            if self.current_task_id and self.current_task_id in self.tasks:
                self.tasks[self.current_task_id]['status'] = 'skipped'
                self.tasks[self.current_task_id]['message'] = '已跳过'
                self.tasks[self.current_task_id]['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                return True
        return False
    
    def retry_all_failed(self) -> int:
        """重试所有失败的任务"""
        with self._lock:
            failed_tasks = [t for t in self.tasks.values() if t['status'] == 'failed']
            for task in failed_tasks:
                task['status'] = 'pending'
                task['message'] = '等待重试'
                task['error'] = None
            return len(failed_tasks)
    
    def clear_queue(self):
        """清空队列"""
        with self._lock:
            self.tasks.clear()
            self.current_task_id = None
    
    def add_downloaded_chapter(self, book_id: str, index: int, content: Dict):
        """添加已下载的章节"""
        with self._lock:
            if book_id not in self.downloaded_chapters:
                self.downloaded_chapters[book_id] = {}
            self.downloaded_chapters[book_id][index] = content
    
    def get_downloaded_chapters(self, book_id: str) -> Dict:
        """获取已下载的章节"""
        with self._lock:
            return self.downloaded_chapters.get(book_id, {}).copy()
    
    def clear_downloaded_chapters(self, book_id: str):
        """清除已下载的章节缓存"""
        with self._lock:
            if book_id in self.downloaded_chapters:
                del self.downloaded_chapters[book_id]


# 全局任务管理器实例
task_manager = TaskManager()
