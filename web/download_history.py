# -*- coding: utf-8 -*-
"""
下载历史管理器
"""

import os
import json
import sys
from datetime import datetime


class DownloadHistoryManager:
    """下载历史管理器"""
    
    def __init__(self):
        self.history_file = self._get_history_file_path()
        self._lock = None
        try:
            import threading
            self._lock = threading.Lock()
        except ImportError:
            pass
    
    def _get_history_file_path(self) -> str:
        """获取历史文件路径"""
        # 获取程序运行目录
        if getattr(sys, 'frozen', False):
            # 打包环境
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            # 开发环境
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 创建 cache 目录
        cache_dir = os.path.join(base_dir, 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        return os.path.join(cache_dir, 'download_history.json')
    
    def _load_history(self) -> list:
        """加载历史记录"""
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    
    def _save_history(self, history: list):
        """保存历史记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def add_record(self, book_id: str, book_name: str, author: str = '', 
                  save_path: str = '', file_format: str = 'txt', 
                  chapter_count: int = 0):
        """添加下载记录"""
        history = self._load_history()
        
        # 检查是否已存在
        for record in history:
            if record.get('book_id') == book_id:
                # 更新现有记录
                record.update({
                    'book_name': book_name,
                    'author': author,
                    'save_path': save_path,
                    'file_format': file_format,
                    'chapter_count': chapter_count,
                    'download_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                self._save_history(history)
                return True
        
        # 添加新记录
        new_record = {
            'book_id': book_id,
            'book_name': book_name,
            'author': author,
            'save_path': save_path,
            'file_format': file_format,
            'chapter_count': chapter_count,
            'download_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        history.append(new_record)
        self._save_history(history)
        return True
    
    def get_all_records(self) -> list:
        """获取所有历史记录"""
        return self._load_history()
    
    def remove_record(self, book_id: str) -> bool:
        """删除指定记录"""
        history = self._load_history()
        original_length = len(history)
        
        history = [r for r in history if r.get('book_id') != book_id]
        
        if len(history) < original_length:
            self._save_history(history)
            return True
        return False
    
    def check_exists(self, book_id: str) -> dict:
        """检查书籍是否已下载"""
        history = self._load_history()
        for record in history:
            if record.get('book_id') == book_id:
                return record
        return None
    
    def check_batch(self, book_ids: list) -> dict:
        """批量检查书籍是否已下载"""
        history = self._load_history()
        history_map = {r.get('book_id'): r for r in history}
        
        results = {}
        for book_id in book_ids:
            results[book_id] = history_map.get(book_id)
        
        return results
    
    def clear_all(self) -> bool:
        """清空所有历史记录"""
        try:
            self._save_history([])
            return True
        except Exception:
            return False


# 全局实例
_download_history_manager = None

def get_download_history_manager():
    """获取下载历史管理器实例"""
    global _download_history_manager
    if _download_history_manager is None:
        _download_history_manager = DownloadHistoryManager()
    return _download_history_manager
