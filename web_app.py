# -*- coding: utf-8 -*-
"""
Web应用程序 - Flask后端，用于HTML GUI
"""

import os
import json
import time
import threading
import queue
import tempfile
import subprocess
import re
import requests
from locales import t
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import logging

# 预先导入版本信息（确保在模块加载时就获取正确版本）
from config import __version__ as APP_VERSION
from config import CONFIG, ConfigLoadError

def _check_config():
    """检查配置是否已加载，返回错误响应或 None"""
    if CONFIG is None:
        return jsonify({
            'success': False,
            'error': '配置加载失败，请检查网络连接',
            'message': '无法连接到配置服务器，应用需要网络连接才能正常使用'
        }), 503
    return None

# 禁用Flask默认日志
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# 访问令牌（由main.py在启动时设置）
ACCESS_TOKEN = None

# 节点探测结果缓存（启动时探测，下载时复用）
# 格式: {base_url: {'available': bool, 'latency_ms': int, 'supports_full_download': bool}}
PROBED_NODES_CACHE = {}

def set_access_token(token):
    """设置访问令牌"""
    global ACCESS_TOKEN
    ACCESS_TOKEN = token

def get_available_nodes() -> list:
    """获取可用节点列表（已探测通过的节点）"""
    return [url for url, info in PROBED_NODES_CACHE.items() if info.get('available')]

def get_full_download_nodes() -> list:
    """获取支持整本下载的可用节点列表"""
    return [url for url, info in PROBED_NODES_CACHE.items()
            if info.get('available') and info.get('supports_full_download')]

def is_node_available(base_url: str) -> bool:
    """检查节点是否可用"""
    base_url = _normalize_base_url(base_url)
    if base_url in PROBED_NODES_CACHE:
        return PROBED_NODES_CACHE[base_url].get('available', False)
    return True  # 未探测的节点默认可用

def update_probed_cache(probed_results: list):
    """更新节点探测缓存"""
    global PROBED_NODES_CACHE
    for result in probed_results:
        base_url = _normalize_base_url(result.get('base_url', ''))
        if base_url:
            PROBED_NODES_CACHE[base_url] = {
                'available': result.get('available', False),
                'latency_ms': result.get('latency_ms'),
                'supports_full_download': result.get('supports_full_download', True),
                'error': result.get('error')
            }

# 配置文件路径 - 保存到系统临时目录（跨平台兼容）
TEMP_DIR = tempfile.gettempdir()
CONFIG_FILE = os.path.join(TEMP_DIR, 'fanqie_novel_downloader_config.json')

def _read_local_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def _write_local_config(updates: dict) -> bool:
    try:
        cfg = _read_local_config()
        cfg.update(updates or {})
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def _normalize_base_url(url: str) -> str:
    return (url or '').strip().rstrip('/')

def get_default_download_path():
    """获取默认下载路径（跨平台兼容）"""
    import sys
    # 优先使用用户下载目录
    home = os.path.expanduser('~')
    if sys.platform == 'win32':
        # Windows: 尝试使用 Downloads 文件夹
        downloads = os.path.join(home, 'Downloads')
    elif sys.platform == 'darwin':
        # macOS
        downloads = os.path.join(home, 'Downloads')
    else:
        # Linux / Termux / 其他 Unix
        downloads = os.path.join(home, 'Downloads')
        # 如果 Downloads 不存在，尝试使用 XDG 用户目录
        if not os.path.exists(downloads):
            xdg_download = os.environ.get('XDG_DOWNLOAD_DIR')
            if xdg_download and os.path.exists(xdg_download):
                downloads = xdg_download
            else:
                # 回退到用户主目录
                downloads = home
    
    # 确保目录存在
    if not os.path.exists(downloads):
        try:
            os.makedirs(downloads, exist_ok=True)
        except:
            downloads = home
    
    return downloads

# ===================== 书籍列表文件解析器 =====================

class BookListParser:
    """解析书籍列表文件
    
    支持格式：
    - 纯书籍ID: 12345
    - 完整URL: https://fanqienovel.com/page/12345
    - 注释行: # 这是注释
    - 空行会被忽略
    """
    
    # URL 正则模式
    URL_PATTERN = re.compile(r'fanqienovel\.com/page/(\d+)')
    
    @staticmethod
    def parse_file_content(content: str) -> dict:
        """
        解析文件内容
        
        Args:
            content: 文件文本内容
        
        Returns:
            {
                'success': bool,
                'books': List[dict],  # [{'book_id': str, 'source_line': int}, ...]
                'skipped': List[dict],  # 跳过的行 [{'line': int, 'content': str, 'reason': str}, ...]
                'total_lines': int
            }
        """
        result = {
            'success': True,
            'books': [],
            'skipped': [],
            'total_lines': 0
        }
        
        if not content or not content.strip():
            return result
        
        lines = content.splitlines()
        result['total_lines'] = len(lines)
        
        seen_ids = set()  # 用于去重
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # 跳过空行
            if not line:
                continue
            
            # 跳过注释行
            if line.startswith('#'):
                continue
            
            # 尝试提取书籍ID
            book_id = BookListParser.extract_book_id(line)
            
            if book_id:
                if book_id not in seen_ids:
                    seen_ids.add(book_id)
                    result['books'].append({
                        'book_id': book_id,
                        'source_line': line_num
                    })
                else:
                    result['skipped'].append({
                        'line': line_num,
                        'content': line[:50] + ('...' if len(line) > 50 else ''),
                        'reason': '重复的书籍ID'
                    })
            else:
                result['skipped'].append({
                    'line': line_num,
                    'content': line[:50] + ('...' if len(line) > 50 else ''),
                    'reason': '无效的格式'
                })
        
        return result
    
    @staticmethod
    def extract_book_id(line: str) -> str:
        """
        从行内容提取书籍ID（支持纯ID和URL格式）
        
        Args:
            line: 单行内容
        
        Returns:
            书籍ID字符串，如果无法提取则返回 None
        """
        line = line.strip()
        
        if not line:
            return None
        
        # 尝试从URL提取
        match = BookListParser.URL_PATTERN.search(line)
        if match:
            return match.group(1)
        
        # 检查是否为纯数字ID
        if line.isdigit() and len(line) >= 5:
            return line
        
        return None


# ===================== 章节范围解析器 =====================

class ChapterRangeParser:
    """解析章节范围输入字符串
    
    支持格式：
    - 单个数字: "5"
    - 范围: "1-100"
    - 多个范围: "1-10, 50-100, 200-300"
    - 混合格式: "1-10, 15, 20-30"
    """
    
    @staticmethod
    def parse(input_str: str, max_chapter: int) -> dict:
        """
        解析章节范围字符串
        
        Args:
            input_str: 用户输入，如 "1-100, 150, 200-300"
            max_chapter: 最大章节数（用于边界验证，1-based）
        
        Returns:
            {
                'success': bool,
                'chapters': List[int],  # 选中的章节索引列表 (0-based)
                'errors': List[str],    # 错误信息列表
                'warnings': List[str]   # 警告信息列表
            }
        """
        result = {
            'success': True,
            'chapters': [],
            'errors': [],
            'warnings': []
        }
        
        # 空输入返回空列表
        if not input_str or not input_str.strip():
            return result
        
        # 分割输入（支持逗号和中文逗号）
        input_str = input_str.replace('，', ',')
        items = [item.strip() for item in input_str.split(',') if item.strip()]
        
        selected_chapters = set()
        
        for item in items:
            parsed = ChapterRangeParser._parse_single_item(item, max_chapter)
            
            if parsed['error']:
                result['errors'].append(parsed['error'])
                result['success'] = False
            elif parsed['warning']:
                result['warnings'].append(parsed['warning'])
                selected_chapters.update(parsed['chapters'])
            else:
                selected_chapters.update(parsed['chapters'])
        
        # 转换为排序后的列表 (0-based 索引)
        result['chapters'] = sorted(list(selected_chapters))
        
        return result
    
    @staticmethod
    def _parse_single_item(item: str, max_chapter: int) -> dict:
        """
        解析单个项目（范围或单个数字）
        
        Args:
            item: 单个项目字符串，如 "1-100" 或 "50"
            max_chapter: 最大章节数 (1-based)
        
        Returns:
            {
                'chapters': List[int],  # 0-based 索引列表
                'error': str or None,
                'warning': str or None
            }
        """
        result = {
            'chapters': [],
            'error': None,
            'warning': None
        }
        
        item = item.strip()
        if not item:
            return result
        
        # 检查是否是范围格式 (支持 - 和 中文 -)
        item = item.replace('－', '-')
        
        if '-' in item:
            parts = item.split('-')
            if len(parts) != 2:
                result['error'] = f'无效的范围格式: "{item}"'
                return result
            
            start_str, end_str = parts[0].strip(), parts[1].strip()
            
            # 验证是否为数字
            if not start_str.isdigit() or not end_str.isdigit():
                result['error'] = f'范围必须是数字: "{item}"'
                return result
            
            start = int(start_str)
            end = int(end_str)
            
            # 验证非负数
            if start <= 0 or end <= 0:
                result['error'] = f'章节号必须大于0: "{item}"'
                return result
            
            # 验证范围有效性
            if start > end:
                result['error'] = f'无效的范围（起始大于结束）: "{item}"'
                return result
            
            # 处理超出最大值的情况
            if start > max_chapter:
                result['warning'] = f'起始章节 {start} 超出最大章节数 {max_chapter}，已忽略'
                return result
            
            if end > max_chapter:
                result['warning'] = f'结束章节 {end} 超出最大章节数 {max_chapter}，已截断到 {max_chapter}'
                end = max_chapter
            
            # 生成章节列表 (转换为 0-based 索引)
            result['chapters'] = list(range(start - 1, end))
            
        else:
            # 单个数字
            if not item.isdigit():
                result['error'] = f'无效的章节号: "{item}"'
                return result
            
            chapter = int(item)
            
            if chapter <= 0:
                result['error'] = f'章节号必须大于0: "{item}"'
                return result
            
            if chapter > max_chapter:
                result['warning'] = f'章节 {chapter} 超出最大章节数 {max_chapter}，已忽略'
                return result
            
            # 转换为 0-based 索引
            result['chapters'] = [chapter - 1]
        
        return result


# ===================== 下载历史管理器 =====================

class DownloadHistoryManager:
    """管理下载历史记录
    
    记录已下载的书籍信息，支持重复下载检测
    """
    
    HISTORY_FILE = 'fanqie_download_history.json'
    
    def __init__(self, history_dir: str = None):
        """
        初始化历史管理器
        
        Args:
            history_dir: 历史文件存储目录，默认为用户目录
        """
        if history_dir:
            self.history_dir = history_dir
        else:
            self.history_dir = os.path.expanduser('~')
        
        self.history_file = os.path.join(self.history_dir, self.HISTORY_FILE)
        self.history = self._load_history()
    
    def _load_history(self) -> dict:
        """从文件加载历史记录"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 验证格式
                    if isinstance(data, dict) and 'records' in data:
                        return data
                    # 兼容旧格式
                    return {'version': 1, 'records': data if isinstance(data, dict) else {}}
            except (json.JSONDecodeError, IOError) as e:
                # 文件损坏，备份并创建新的
                backup_file = self.history_file + '.bak'
                try:
                    if os.path.exists(self.history_file):
                        os.rename(self.history_file, backup_file)
                except:
                    pass
                return {'version': 1, 'records': {}}
        return {'version': 1, 'records': {}}
    
    def _save_history(self) -> bool:
        """保存历史记录到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            return True
        except IOError:
            return False
    
    def add_record(self, book_id: str, book_name: str, author: str,
                   save_path: str, file_format: str, chapter_count: int = 0) -> bool:
        """
        添加下载记录
        
        Args:
            book_id: 书籍ID
            book_name: 书名
            author: 作者
            save_path: 保存路径
            file_format: 文件格式 (txt/epub)
            chapter_count: 章节数量
        
        Returns:
            是否保存成功
        """
        from datetime import datetime
        
        record = {
            'book_id': str(book_id),
            'book_name': book_name,
            'author': author,
            'download_time': datetime.now().isoformat(),
            'save_path': save_path,
            'file_format': file_format,
            'chapter_count': chapter_count
        }
        
        self.history['records'][str(book_id)] = record
        return self._save_history()
    
    def check_exists(self, book_id: str) -> dict:
        """
        检查书籍是否已下载
        
        Args:
            book_id: 书籍ID
        
        Returns:
            如果存在返回记录详情，否则返回 None
        """
        book_id = str(book_id)
        record = self.history['records'].get(book_id)
        
        if record:
            # 检查文件是否仍然存在
            record = record.copy()
            record['file_exists'] = os.path.exists(record.get('save_path', ''))
            return record
        
        return None
    
    def check_batch(self, book_ids: list) -> dict:
        """
        批量检查书籍是否已下载
        
        Args:
            book_ids: 书籍ID列表
        
        Returns:
            {book_id: record_or_none, ...}
        """
        result = {}
        for book_id in book_ids:
            result[str(book_id)] = self.check_exists(book_id)
        return result
    
    def get_all_records(self) -> list:
        """获取所有下载记录"""
        records = []
        for book_id, record in self.history['records'].items():
            record_copy = record.copy()
            record_copy['file_exists'] = os.path.exists(record.get('save_path', ''))
            records.append(record_copy)
        
        # 按下载时间倒序排列
        records.sort(key=lambda x: x.get('download_time', ''), reverse=True)
        return records
    
    def remove_record(self, book_id: str) -> bool:
        """
        删除下载记录
        
        Args:
            book_id: 书籍ID
        
        Returns:
            是否删除成功
        """
        book_id = str(book_id)
        if book_id in self.history['records']:
            del self.history['records'][book_id]
            return self._save_history()
        return False
    
    def clear_all(self) -> bool:
        """清空所有历史记录"""
        self.history['records'] = {}
        return self._save_history()


# 全局下载历史管理器实例
_download_history_manager = None

def get_download_history_manager() -> DownloadHistoryManager:
    """获取下载历史管理器单例"""
    global _download_history_manager
    if _download_history_manager is None:
        _download_history_manager = DownloadHistoryManager()
    return _download_history_manager


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
    'messages': []  # 消息队列，存储所有待传递的消息
}
status_lock = threading.Lock()


# ===================== 任务管理器 =====================

class TaskManager:
    """下载队列任务管理器
    
    管理下载任务列表、状态跟踪、跳过/重试/强制保存等操作
    """
    
    # 任务状态常量
    STATUS_PENDING = 'pending'
    STATUS_DOWNLOADING = 'downloading'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'
    
    def __init__(self):
        self.tasks = []  # 任务列表
        self.current_index = 0  # 当前任务索引
        self.is_running = False  # 队列是否正在运行
        self.skip_requested = False  # 是否请求跳过当前任务
        self.force_save_requested = False  # 是否请求强制保存
        self.current_download_mode = None  # 当前下载模式 (fast/slow)
        self.downloaded_chapters = {}  # 已下载章节 {book_id: {index: content}}
        self._lock = threading.Lock()
    
    def start_queue(self, tasks: list) -> bool:
        """启动队列下载
        
        Args:
            tasks: 任务列表，每个任务包含 book_id, book_name, author 等信息
        
        Returns:
            bool: 是否成功启动
        """
        with self._lock:
            if self.is_running:
                return False
            
            self.tasks = []
            for i, task in enumerate(tasks):
                self.tasks.append({
                    'id': task.get('id', f"task_{i}_{int(time.time())}"),
                    'book_id': task.get('book_id'),
                    'book_name': task.get('book_name', ''),
                    'author': task.get('author', ''),
                    'status': self.STATUS_PENDING,
                    'progress': 0,
                    'error_message': None,
                    'file_format': task.get('file_format', 'txt'),
                    'save_path': task.get('save_path', ''),
                    'start_chapter': task.get('start_chapter'),
                    'end_chapter': task.get('end_chapter'),
                    'selected_chapters': task.get('selected_chapters'),
                    'created_at': time.time(),
                    'started_at': None,
                    'completed_at': None
                })
            
            self.current_index = 0
            self.is_running = True
            self.skip_requested = False
            self.force_save_requested = False
            
            return True
    
    def get_current_task(self) -> dict:
        """获取当前正在执行的任务"""
        with self._lock:
            if 0 <= self.current_index < len(self.tasks):
                return self.tasks[self.current_index].copy()
            return None
    
    def update_task_status(self, task_id: str, status: str, progress: int = None, 
                          error_message: str = None) -> bool:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度 (0-100)
            error_message: 错误信息
        
        Returns:
            bool: 是否更新成功
        """
        with self._lock:
            for task in self.tasks:
                if task['id'] == task_id:
                    task['status'] = status
                    if progress is not None:
                        task['progress'] = progress
                    if error_message is not None:
                        task['error_message'] = error_message
                    
                    if status == self.STATUS_DOWNLOADING and task['started_at'] is None:
                        task['started_at'] = time.time()
                    elif status in [self.STATUS_COMPLETED, self.STATUS_FAILED, self.STATUS_SKIPPED]:
                        task['completed_at'] = time.time()
                    
                    return True
            return False
    
    def skip_current(self) -> bool:
        """跳过当前任务
        
        Returns:
            bool: 是否成功设置跳过标志
        """
        with self._lock:
            if not self.is_running:
                return False
            
            if 0 <= self.current_index < len(self.tasks):
                current_task = self.tasks[self.current_index]
                if current_task['status'] == self.STATUS_DOWNLOADING:
                    self.skip_requested = True
                    current_task['status'] = self.STATUS_SKIPPED
                    current_task['completed_at'] = time.time()
                    return True
            return False
    
    def force_save(self) -> dict:
        """强制保存当前已下载的内容
        
        Returns:
            dict: 保存结果，包含 success, saved_chapters, book_id
        """
        with self._lock:
            if not self.is_running:
                return {'success': False, 'message': '队列未运行'}
            
            current_task = self.get_current_task_unsafe()
            if not current_task:
                return {'success': False, 'message': '没有正在执行的任务'}
            
            book_id = current_task['book_id']
            
            # 设置强制保存标志
            self.force_save_requested = True
            
            # 获取已下载的章节
            downloaded = self.downloaded_chapters.get(book_id, {})
            
            return {
                'success': True,
                'book_id': book_id,
                'saved_chapters': len(downloaded),
                'message': f'已保存 {len(downloaded)} 个章节'
            }
    
    def get_current_task_unsafe(self) -> dict:
        """获取当前任务（不加锁，内部使用）"""
        if 0 <= self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return None
    
    def move_to_next_task(self) -> bool:
        """移动到下一个任务
        
        Returns:
            bool: 是否还有下一个任务
        """
        with self._lock:
            self.current_index += 1
            self.skip_requested = False
            self.force_save_requested = False
            
            if self.current_index >= len(self.tasks):
                self.is_running = False
                return False
            return True
    
    def retry_task(self, task_id: str) -> bool:
        """重试指定任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            bool: 是否成功设置重试
        """
        with self._lock:
            for task in self.tasks:
                if task['id'] == task_id and task['status'] == self.STATUS_FAILED:
                    task['status'] = self.STATUS_PENDING
                    task['progress'] = 0
                    task['error_message'] = None
                    task['started_at'] = None
                    task['completed_at'] = None
                    return True
            return False
    
    def retry_all_failed(self) -> int:
        """重试所有失败的任务
        
        Returns:
            int: 重试的任务数量
        """
        with self._lock:
            count = 0
            for task in self.tasks:
                if task['status'] == self.STATUS_FAILED:
                    task['status'] = self.STATUS_PENDING
                    task['progress'] = 0
                    task['error_message'] = None
                    task['started_at'] = None
                    task['completed_at'] = None
                    count += 1
            return count
    
    def get_queue_status(self) -> dict:
        """获取队列状态
        
        Returns:
            dict: 队列状态信息
        """
        with self._lock:
            completed_count = sum(1 for t in self.tasks if t['status'] == self.STATUS_COMPLETED)
            failed_count = sum(1 for t in self.tasks if t['status'] == self.STATUS_FAILED)
            skipped_count = sum(1 for t in self.tasks if t['status'] == self.STATUS_SKIPPED)
            
            current_task = self.get_current_task_unsafe()
            current_task_id = current_task['id'] if current_task else None
            current_task_progress = current_task['progress'] if current_task else 0
            
            return {
                'is_running': self.is_running,
                'total_tasks': len(self.tasks),
                'completed_count': completed_count,
                'failed_count': failed_count,
                'skipped_count': skipped_count,
                'current_task_id': current_task_id,
                'current_task_progress': current_task_progress,
                'current_download_mode': self.current_download_mode,
                'tasks': [t.copy() for t in self.tasks]
            }
    
    def set_download_mode(self, mode: str):
        """设置当前下载模式
        
        Args:
            mode: 'fast' 或 'slow'
        """
        with self._lock:
            self.current_download_mode = mode
    
    def store_chapter(self, book_id: str, chapter_index: int, content: dict):
        """存储已下载的章节内容
        
        Args:
            book_id: 书籍ID
            chapter_index: 章节索引
            content: 章节内容
        """
        with self._lock:
            if book_id not in self.downloaded_chapters:
                self.downloaded_chapters[book_id] = {}
            self.downloaded_chapters[book_id][chapter_index] = content
    
    def get_downloaded_chapters(self, book_id: str) -> dict:
        """获取已下载的章节
        
        Args:
            book_id: 书籍ID
        
        Returns:
            dict: 已下载的章节 {index: content}
        """
        with self._lock:
            return self.downloaded_chapters.get(book_id, {}).copy()
    
    def clear_downloaded_chapters(self, book_id: str):
        """清除已下载的章节缓存
        
        Args:
            book_id: 书籍ID
        """
        with self._lock:
            if book_id in self.downloaded_chapters:
                del self.downloaded_chapters[book_id]


# 全局任务管理器实例
task_manager = TaskManager()


# 更新下载状态 - 支持多线程下载
update_download_status = {
    'is_downloading': False,
    'progress': 0,
    'message': '',
    'filename': '',
    'total_size': 0,
    'downloaded_size': 0,
    'completed': False,
    'error': None,
    'save_path': '',
    'temp_file_path': '',
    'thread_count': 1,
    'thread_progress': [],  # 每个线程的进度 [{'downloaded': 50, 'total': 100, 'percent': 50, 'speed': 1024}, ...]
    'merging': False  # 是否正在合并文件
}
update_lock = threading.Lock()

def get_update_status():
    """获取更新下载状态"""
    with update_lock:
        return update_download_status.copy()

def set_update_status(**kwargs):
    """设置更新下载状态"""
    with update_lock:
        for key, value in kwargs.items():
            if key in update_download_status:
                update_download_status[key] = value

def test_url_connectivity(url, timeout=8):
    """测试 URL 连通性"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    test_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # requests 默认会使用系统代理，直接测试即可
    print(f'[DEBUG] Testing connection to: {test_url}')
    try:
        resp = requests.head(test_url, timeout=timeout, allow_redirects=True)
        if resp.status_code < 500:
            print(f'[DEBUG] Connection OK (status: {resp.status_code})')
            return True
    except Exception as e:
        print(f'[DEBUG] Connection failed: {e}')
    
    return False

def download_chunk_adaptive(url, start, end, chunk_id, temp_file, progress_dict, total_size, cancel_flag):
    """下载文件的一个分块（极速版本）"""
    headers = {'Range': f'bytes={start}-{end}'}
    try:
        # 使用更大的缓冲区和更短的超时
        response = requests.get(url, headers=headers, stream=True, timeout=60, allow_redirects=True)
        response.raise_for_status()

        chunk_size = 131072  # 128KB chunks for maximum throughput
        downloaded = 0
        chunk_total = end - start + 1
        last_time = time.time()
        last_downloaded = 0

        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if cancel_flag.get('cancelled'):
                    return {'success': False, 'reason': 'cancelled'}
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # 减少进度更新频率，提高性能
                    now = time.time()
                    if now - last_time >= 0.2:  # 每200ms更新一次
                        speed = (downloaded - last_downloaded) / (now - last_time)
                        last_time = now
                        last_downloaded = downloaded
                        progress_dict[chunk_id] = {
                            'downloaded': downloaded,
                            'total': chunk_total,
                            'percent': int((downloaded / chunk_total) * 100) if chunk_total > 0 else 0,
                            'speed': speed
                        }

        # 最终更新
        progress_dict[chunk_id] = {
            'downloaded': chunk_total,
            'total': chunk_total,
            'percent': 100,
            'speed': 0
        }
        return {'success': True, 'chunk_id': chunk_id}
    except Exception as e:
        print(f'[DEBUG] Chunk {chunk_id} download error: {e}')
        return {'success': False, 'reason': str(e), 'chunk_id': chunk_id}

def update_download_worker(url, save_path, filename):
    """更新下载工作线程 - 极速多线程下载"""
    print(f'[DEBUG] update_download_worker started (extreme speed multi-threaded)')
    print(f'[DEBUG]   url: {url}')
    print(f'[DEBUG]   save_path: {save_path}')
    print(f'[DEBUG]   filename: {filename}')

    # 极速配置
    INITIAL_THREADS = 16      # 初始线程数，直接拉满
    MAX_THREADS = 32          # 最大线程数
    MIN_CHUNK_SIZE = 512 * 1024  # 最小分块 512KB

    try:
        set_update_status(
            is_downloading=True,
            progress=0,
            message=t('web_update_status_connect'),
            filename=filename,
            completed=False,
            error=None,
            save_path=save_path,
            thread_count=INITIAL_THREADS,
            thread_progress=[],
            merging=False
        )

        import tempfile
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 快速连通性测试
        set_update_status(message=t('web_update_status_connect'))
        if not test_url_connectivity(url, timeout=5):
            raise Exception(t('web_update_connect_fail'))

        # 获取文件大小
        print(f'[DEBUG] Getting file info from: {url}')
        head_response = requests.get(url, stream=True, timeout=15, allow_redirects=True)
        head_response.raise_for_status()

        final_url = head_response.url
        print(f'[DEBUG] Final URL after redirect: {final_url}')

        total_size = int(head_response.headers.get('content-length', 0))
        supports_range = head_response.headers.get('accept-ranges', '').lower() == 'bytes'
        head_response.close()

        print(f'[DEBUG] Total size: {total_size} bytes, supports_range: {supports_range}')

        temp_dir = tempfile.gettempdir()
        temp_filename = filename + '.new'
        full_path = os.path.join(temp_dir, temp_filename)

        # 不支持分块或文件太小，使用单线程
        if total_size == 0 or not supports_range or total_size < 2 * 1024 * 1024:
            print(f'[DEBUG] Using single-threaded download (file too small or no range support)')
            set_update_status(thread_count=1, total_size=total_size, message=t('web_update_status_start'))

            response = requests.get(final_url, stream=True, timeout=120, allow_redirects=True)
            response.raise_for_status()

            if total_size == 0:
                total_size = int(response.headers.get('content-length', 0))

            downloaded = 0
            last_update = time.time()
            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):  # 64KB
                    if not get_update_status()['is_downloading']:
                        break
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if now - last_update >= 0.1:  # 每100ms更新
                            progress = int((downloaded / total_size) * 100) if total_size > 0 else min(99, downloaded // 100000)
                            set_update_status(
                                progress=progress,
                                downloaded_size=downloaded,
                                total_size=total_size,
                                thread_progress=[{'downloaded': downloaded, 'total': total_size or downloaded, 'percent': progress, 'speed': 0}],
                                message=t('web_update_status_dl', progress) if total_size > 0 else f'已下载 {downloaded // 1024} KB'
                            )
                            last_update = now
        else:
            # 极速多线程下载
            print(f'[DEBUG] Using extreme speed multi-threaded download')

            # 计算最优线程数和分块大小
            optimal_threads = min(MAX_THREADS, max(INITIAL_THREADS, total_size // (1024 * 1024)))  # 每MB一个线程，最多MAX_THREADS
            chunk_size = max(MIN_CHUNK_SIZE, total_size // optimal_threads)

            print(f'[DEBUG] Optimal threads: {optimal_threads}, chunk size: {chunk_size}')
            set_update_status(total_size=total_size, thread_count=optimal_threads, message=t('web_update_status_start'))

            cancel_flag = {'cancelled': False}
            progress_dict = {}
            chunks = []

            # 预先分配所有分块
            start = 0
            chunk_id = 0
            while start < total_size:
                end = min(start + chunk_size - 1, total_size - 1)
                temp_file = os.path.join(temp_dir, f'{filename}.part{chunk_id}')
                chunks.append((chunk_id, start, end, temp_file))
                start = end + 1
                chunk_id += 1

            print(f'[DEBUG] Total chunks: {len(chunks)}')

            completed_chunks = []
            failed_chunks = []

            def update_progress():
                """更新总进度"""
                total_downloaded = sum(p.get('downloaded', 0) for p in progress_dict.values())
                overall_progress = int((total_downloaded / total_size) * 100) if total_size > 0 else 0
                overall_progress = min(99, overall_progress)

                thread_progress = [
                    {'downloaded': p.get('downloaded', 0), 'total': p.get('total', 0), 'percent': p.get('percent', 0), 'speed': p.get('speed', 0)}
                    for p in progress_dict.values()
                ]

                set_update_status(
                    progress=overall_progress,
                    downloaded_size=total_downloaded,
                    thread_count=len([p for p in progress_dict.values() if p.get('percent', 0) < 100]),
                    thread_progress=thread_progress,
                    message=t('web_update_status_dl', overall_progress)
                )
                return total_downloaded

            # 使用线程池并发下载所有分块
            with ThreadPoolExecutor(max_workers=optimal_threads) as executor:
                # 提交所有任务
                future_to_chunk = {}
                for chunk_info in chunks:
                    chunk_id, start, end, temp_file = chunk_info
                    future = executor.submit(
                        download_chunk_adaptive, final_url, start, end,
                        chunk_id, temp_file, progress_dict, total_size, cancel_flag
                    )
                    future_to_chunk[future] = chunk_info

                # 监控进度
                last_progress_update = time.time()
                while future_to_chunk:
                    if not get_update_status()['is_downloading']:
                        cancel_flag['cancelled'] = True
                        # 取消所有未完成的任务
                        for future in future_to_chunk:
                            future.cancel()
                        break

                    # 检查已完成的任务
                    done_futures = [f for f in future_to_chunk if f.done()]
                    for future in done_futures:
                        chunk_info = future_to_chunk.pop(future)
                        chunk_id, start, end, temp_file = chunk_info
                        try:
                            result = future.result()
                            if result.get('success'):
                                completed_chunks.append(chunk_info)
                            else:
                                print(f'[DEBUG] Chunk {chunk_id} failed: {result.get("reason")}')
                                failed_chunks.append(chunk_info)
                        except Exception as e:
                            print(f'[DEBUG] Chunk {chunk_id} exception: {e}')
                            failed_chunks.append(chunk_info)

                    # 更新进度（每50ms）
                    now = time.time()
                    if now - last_progress_update >= 0.05:
                        update_progress()
                        last_progress_update = now

                    time.sleep(0.01)  # 极短休眠，快速响应

                # 重试失败的分块
                retry_count = 0
                while failed_chunks and retry_count < 3 and not cancel_flag['cancelled']:
                    retry_count += 1
                    print(f'[DEBUG] Retrying {len(failed_chunks)} failed chunks (attempt {retry_count})')

                    retry_futures = {}
                    for chunk_info in failed_chunks:
                        chunk_id, start, end, temp_file = chunk_info
                        future = executor.submit(
                            download_chunk_adaptive, final_url, start, end,
                            chunk_id, temp_file, progress_dict, total_size, cancel_flag
                        )
                        retry_futures[future] = chunk_info

                    failed_chunks = []
                    for future in as_completed(retry_futures):
                        if cancel_flag['cancelled']:
                            break
                        chunk_info = retry_futures[future]
                        try:
                            result = future.result()
                            if result.get('success'):
                                completed_chunks.append(chunk_info)
                            else:
                                failed_chunks.append(chunk_info)
                        except Exception:
                            failed_chunks.append(chunk_info)

            if cancel_flag['cancelled']:
                # 清理临时文件
                for chunk_info in completed_chunks:
                    _, _, _, temp_file = chunk_info
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                print(f'[DEBUG] Download was cancelled')
                return

            if failed_chunks:
                raise Exception(f'部分分块下载失败: {len(failed_chunks)} 个')

            # 合并文件
            if completed_chunks and get_update_status()['is_downloading']:
                print(f'[DEBUG] Merging {len(completed_chunks)} chunks...')
                set_update_status(
                    progress=100,
                    message=t('web_update_status_merging'),
                    merging=True
                )
                
                # 按 chunk_id 排序
                completed_chunks.sort(key=lambda x: x[0])
                
                with open(full_path, 'wb') as outfile:
                    for chunk_id, start, end, temp_file in completed_chunks:
                        if os.path.exists(temp_file):
                            with open(temp_file, 'rb') as infile:
                                outfile.write(infile.read())
                            os.remove(temp_file)
                            print(f'[DEBUG] Merged chunk {chunk_id}')
            else:
                # 清理临时文件
                for chunk_id, start, end, temp_file in completed_chunks:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
        
        if get_update_status()['is_downloading']:
            print(f'[DEBUG] Download completed successfully!')
            print(f'[DEBUG] File saved to: {full_path}')
            if os.path.exists(full_path):
                print(f'[DEBUG] File size: {os.path.getsize(full_path)} bytes')
            set_update_status(
                is_downloading=False, 
                completed=True, 
                progress=100, 
                message=t('web_update_complete'),
                temp_file_path=full_path,
                merging=False
            )
        else:
            print(f'[DEBUG] Download was cancelled')
            if os.path.exists(full_path):
                os.remove(full_path)
                
    except Exception as e:
        import traceback
        print(f'[DEBUG] Download failed with exception:')
        print(f'[DEBUG]   {type(e).__name__}: {str(e)}')
        traceback.print_exc()
        set_update_status(
            is_downloading=False, 
            error=str(e), 
            message=t('web_update_fail', str(e)),
            merging=False
        )

# 延迟导入重型模块
api = None
api_manager = None
novel_downloader = None
downloader_instance = None

def init_modules(skip_api_select=False):
    """初始化核心模块"""
    global api, api_manager, novel_downloader, downloader_instance
    try:
        # 若未指定接口则自动选择一个可用的（可跳过以加速启动）
        if not skip_api_select:
            _ensure_api_base_url()

        from novel_downloader import NovelDownloader, get_api_manager
        novel_downloader = __import__('novel_downloader')
        api = NovelDownloader()
        api_manager = get_api_manager()
        downloader_instance = api
        return True
    except Exception as e:
        print(t("msg_module_fail", e))
        return False


def _get_api_sources() -> list:
    """从配置获取可选 API 接口列表"""
    try:
        if CONFIG is None:
            return []
        sources = CONFIG.get('api_sources') or []
        normalized = []
        for s in sources:
            if isinstance(s, dict):
                base_url = _normalize_base_url(s.get('base_url') or s.get('api_base_url') or '')
                if base_url:
                    normalized.append({
                        'name': s.get('name') or base_url,
                        'base_url': base_url
                    })
            elif isinstance(s, str):
                base_url = _normalize_base_url(s)
                if base_url:
                    normalized.append({'name': base_url, 'base_url': base_url})

        # 回退：至少包含当前 base_url
        base = _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))
        if base and not any(x['base_url'] == base for x in normalized):
            normalized.insert(0, {'name': base, 'base_url': base})

        # 去重
        seen = set()
        deduped = []
        for s in normalized:
            if s['base_url'] in seen:
                continue
            seen.add(s['base_url'])
            deduped.append(s)

        return deduped
    except Exception:
        return []


def _probe_api_source(base_url: str, timeout: float = 1.5) -> dict:
    """HTTP 探活（仅 ping 域名根路径，快速超时）"""
    import requests
    from urllib.parse import urlparse

    base_url = _normalize_base_url(base_url)
    parsed = urlparse(base_url)
    ping_url = f"{parsed.scheme}://{parsed.netloc}/"

    start = time.perf_counter()
    try:
        resp = requests.head(ping_url, timeout=timeout, allow_redirects=True)
        latency_ms = int((time.perf_counter() - start) * 1000)

        # 只要能连上就认为可用
        available = resp.status_code < 500
        return {
            'available': available,
            'latency_ms': latency_ms,
            'status_code': resp.status_code,
            'error': None
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            'available': False,
            'latency_ms': latency_ms,
            'status_code': None,
            'error': str(e)
        }


def _apply_api_base_url(base_url: str) -> None:
    """应用 API base_url 到运行时（CONFIG + APIManager）"""
    if CONFIG is None:
        return

    base_url = _normalize_base_url(base_url)
    if not base_url:
        return

    CONFIG['api_base_url'] = base_url

    global api_manager
    if api_manager:
        api_manager.base_url = base_url
        # 重置线程局部 Session，避免连接复用导致的问题
        if hasattr(api_manager, '_tls'):
            api_manager._tls = threading.local()


def _ensure_api_base_url(force_mode=None) -> str:
    """
    确保 CONFIG.api_base_url 已设置；若为空/不可用则自动选择最快节点。

    Returns:
        str: 当前/选中的 base_url（可能为空）
    """
    if CONFIG is None:
        return ''

    sources = _get_api_sources()
    if not sources:
        return _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))

    local_cfg = _read_local_config()
    mode = str(local_cfg.get('api_base_url_mode', 'auto') or 'auto').lower()
    if force_mode:
        mode = str(force_mode).lower()

    current = _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))

    # 手动模式优先
    if mode == 'manual':
        manual_url = _normalize_base_url(str(local_cfg.get('api_base_url', '') or ''))
        if manual_url:
            probe = _probe_api_source(manual_url, timeout=1.5)
            if probe.get('available'):
                _apply_api_base_url(manual_url)
                return manual_url

    # 并发探测全部并选择延迟最低的可用项
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []
    with ThreadPoolExecutor(max_workers=min(10, len(sources))) as ex:
        fut_map = {ex.submit(_probe_api_source, s['base_url'], 1.5): s for s in sources}
        for fut in as_completed(fut_map):
            src = fut_map[fut]
            try:
                probe = fut.result()
            except Exception as e:
                probe = {'available': False, 'latency_ms': None, 'status_code': None, 'error': str(e)}
            results.append({**src, **probe})

    # 按延迟排序，选择最快的可用节点
    available = [r for r in results if r.get('available')]
    available.sort(key=lambda x: (x.get('latency_ms') or 999999))

    if available:
        best = available[0]['base_url']
        _apply_api_base_url(best)
        _write_local_config({'api_base_url_mode': 'auto', 'api_base_url': best})
        return best

    # 若没有可用项，仍返回当前（可能为空）
    return current

def get_status():
    """获取当前下载状态"""
    with status_lock:
        status = current_download_status.copy()
        # 获取并清空消息队列
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
            # 将消息添加到队列（用于前端显示完整日志）
            current_download_status['messages'].append(message)
            # 限制队列长度，防止内存溢出
            if len(current_download_status['messages']) > 100:
                current_download_status['messages'] = current_download_status['messages'][-50:]
        for key, value in kwargs.items():
            if key in current_download_status:
                current_download_status[key] = value

def download_worker():
    """后台下载工作线程"""
    while True:
        try:
            task = download_queue.get(timeout=1)
            if task is None:
                break
            
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

            update_status(is_downloading=True, progress=0, message=t('web_init'))
            
            if not api:
                update_status(message=t('web_api_not_init'), progress=0, is_downloading=False)
                continue
            
            try:
                # 设置进度回调
                def progress_callback(progress, message):
                    if progress >= 0:
                        update_status(progress=progress, message=message)
                    else:
                        update_status(message=message)
                
                # 强制刷新 API 实例，防止线程间 Session 污染
                if hasattr(api_manager, '_tls'):
                    api_manager._tls = threading.local()
                
                # 获取书籍信息
                update_status(message=t('web_connecting_book'))
                
                # 增加超时重试机制
                book_detail = None
                for _ in range(3):
                    book_detail = api_manager.get_book_detail(book_id)
                    if book_detail:
                        break
                    time.sleep(1)
                
                if not book_detail:
                    update_status(message=t('web_book_info_fail_check'), is_downloading=False)
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
                update_status(book_name=book_name, message=t('web_preparing_download', book_name))
                
                # 执行下载
                update_status(message=t('web_starting_engine'))
                success = api.run_download(book_id, save_path, file_format, start_chapter, end_chapter, selected_chapters, progress_callback)

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
                        from novel_downloader import sanitize_filename, generate_filename
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
                            message=t('web_queue_next', queue_done, queue_total),
                            is_downloading=True,
                            queue_current=min(queue_done + 1, queue_total)
                        )
                    else:
                        if queue_total > 0:
                            update_status(
                                progress=100,
                                message=t('web_queue_complete', queue_total, save_path),
                                is_downloading=False,
                                queue_total=0,
                                queue_done=0,
                                queue_current=0
                            )
                        else:
                            update_status(progress=100, message=t('web_download_success_path', save_path), is_downloading=False)
                else:
                    if has_more:
                        update_status(
                            progress=0,
                            message=t('web_queue_next_fail', queue_done, queue_total),
                            is_downloading=True,
                            queue_current=min(queue_done + 1, queue_total)
                        )
                    else:
                        if queue_total > 0:
                            update_status(
                                progress=0,
                                message=t('web_queue_complete_fail', queue_total, save_path),
                                is_downloading=False,
                                queue_total=0,
                                queue_done=0,
                                queue_current=0
                            )
                        else:
                            update_status(message=t('web_download_interrupted'), progress=0, is_downloading=False)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_str = str(e)
                update_status(message=t('web_download_exception', error_str), progress=0, is_downloading=False)
                print(f"下载异常: {error_str}")
        
        except queue.Empty:
            continue
        except Exception as e:
            error_str = str(e)
            update_status(message=t('web_worker_error', error_str), progress=0, is_downloading=False)
            print(f"工作线程异常: {error_str}")

# 启动后台下载线程
download_thread = threading.Thread(target=download_worker, daemon=True)
download_thread.start()

# ===================== 访问控制中间件 =====================

@app.before_request
def check_access():
    """请求前验证访问令牌"""
    # 静态文件不需要验证
    if request.path.startswith('/static/'):
        return None
    
    # 验证token
    if ACCESS_TOKEN is not None:
        token = request.args.get('token') or request.headers.get('X-Access-Token')
        if token != ACCESS_TOKEN:
            return jsonify({'error': 'Forbidden'}), 403
    
    return None

# ===================== API 路由 =====================

@app.route('/')
def index():
    """主页"""
    from config import __version__
    token = request.args.get('token', '')
    return render_template('index.html', version=__version__, access_token=token)

@app.route('/api/init', methods=['POST'])
def api_init():
    """初始化模块（跳过节点探测，由前端单独调用 /api/api-sources）"""
    if init_modules(skip_api_select=True):
        return jsonify({'success': True, 'message': t('web_module_loaded')})
    return jsonify({'success': False, 'message': t('web_module_fail_msg')}), 500

@app.route('/api/version', methods=['GET'])
def api_version():
    """获取当前版本号"""
    from config import __version__
    return jsonify({'success': True, 'version': __version__})

@app.route('/api/status', methods=['GET'])
def api_status():
    """获取下载状态"""
    return jsonify(get_status())


@app.route('/api/api-sources', methods=['GET'])
def api_api_sources():
    """获取可用的下载接口列表，并返回可用性探测结果（并发探测）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 检查配置是否可用
    config_error = _check_config()
    if config_error:
        return config_error

    local_cfg = _read_local_config()
    mode = str(local_cfg.get('api_base_url_mode', 'auto') or 'auto').lower()
    sources = _get_api_sources()

    # 并发探测所有节点
    timeout = min(float(CONFIG.get('request_timeout', 10) or 10), 2.0)
    probed = []
    with ThreadPoolExecutor(max_workers=min(10, len(sources) or 1)) as ex:
        fut_map = {ex.submit(_probe_api_source, s['base_url'], timeout): s for s in sources}
        for fut in as_completed(fut_map):
            src = fut_map[fut]
            try:
                probe = fut.result()
            except Exception as e:
                probe = {'available': False, 'latency_ms': None, 'status_code': None, 'error': str(e)}
            probed.append({**src, **probe})

    # 更新节点探测缓存（供下载时使用，跳过不可用节点）
    update_probed_cache(probed)

    # 按延迟排序
    probed.sort(key=lambda x: (not x.get('available'), x.get('latency_ms') or 999999))

    # 自动模式下选择最快的可用节点
    current = _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))
    if mode == 'auto':
        available = [p for p in probed if p.get('available')]
        if available:
            best = available[0]['base_url']
            if best != current:
                _apply_api_base_url(best)
                _write_local_config({'api_base_url_mode': 'auto', 'api_base_url': best})
            current = best

    return jsonify({
        'success': True,
        'mode': mode,
        'current': current,
        'sources': probed
    })


@app.route('/api/api-sources/select', methods=['POST'])
def api_api_sources_select():
    """选择下载接口（manual/auto），并在选择时自动探测可用性"""
    data = request.get_json() or {}
    mode = str(data.get('mode', 'auto') or 'auto').lower()

    if mode not in ['auto', 'manual']:
        mode = 'auto'

    if mode == 'auto':
        selected = _ensure_api_base_url(force_mode='auto')
        if not selected:
            return jsonify({'success': False, 'message': '未找到可用接口'}), 500
        _write_local_config({'api_base_url_mode': 'auto', 'api_base_url': selected})
        return jsonify({'success': True, 'mode': 'auto', 'current': selected})

    # manual
    base_url = _normalize_base_url(str(data.get('base_url', '') or ''))
    if not base_url:
        return jsonify({'success': False, 'message': 'base_url required'}), 400

    probe = _probe_api_source(base_url)
    if not probe.get('available'):
        err = probe.get('error') or 'unavailable'
        return jsonify({'success': False, 'message': f'接口不可用: {base_url} ({err})', 'probe': probe}), 400

    _apply_api_base_url(base_url)
    _write_local_config({'api_base_url_mode': 'manual', 'api_base_url': base_url})

    return jsonify({'success': True, 'mode': 'manual', 'current': base_url, 'probe': probe})

@app.route('/api/search', methods=['POST'])
def api_search():
    """搜索书籍"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    offset = data.get('offset', 0)
    
    if not keyword:
        return jsonify({'success': False, 'message': t('web_search_keyword_empty')}), 400
    
    if not api_manager:
        return jsonify({'success': False, 'message': t('web_api_not_init')}), 500
    
    try:
        result = api_manager.search_books(keyword, offset)
        if result and result.get('data'):
            # 解析搜索结果
            search_data = result.get('data', {})
            books = []
            has_more = False
            
            # 新 API 数据结构: data.search_tabs[].data[].book_data[]
            # 需要找到 tab_type=3 (书籍) 的 tab
            search_tabs = search_data.get('search_tabs', [])
            for tab in search_tabs:
                if tab.get('tab_type') == 3:  # 书籍 tab
                    has_more = tab.get('has_more', False)
                    tab_data = tab.get('data', [])
                    if isinstance(tab_data, list):
                        for item in tab_data:
                            # 每个 item 包含 book_data 数组
                            book_data_list = item.get('book_data', [])
                            for book in book_data_list:
                                if isinstance(book, dict):
                                    # 解析字数 (可能是字符串)
                                    word_count = book.get('word_number', 0) or book.get('word_count', 0)
                                    if isinstance(word_count, str):
                                        try:
                                            word_count = int(word_count)
                                        except:
                                            word_count = 0
                                    
                                    # 解析章节数
                                    chapter_count = book.get('serial_count', 0) or book.get('chapter_count', 0)
                                    if isinstance(chapter_count, str):
                                        try:
                                            chapter_count = int(chapter_count)
                                        except:
                                            chapter_count = 0
                                    
                                    # 解析状态 (0=已完结, 1=连载中, 2=完结)
                                    status_code = book.get('creation_status', '')
                                    # 转换为字符串进行比较
                                    status_code_str = str(status_code) if status_code is not None else ''
                                    if status_code_str == '0':
                                        status = t('dl_status_finished')
                                    elif status_code_str == '1':
                                        status = t('dl_status_serializing')
                                    elif status_code_str == '2':
                                        status = t('dl_status_completed_2')
                                    else:
                                        status = ''
                                    
                                    books.append({
                                        'book_id': str(book.get('book_id', '')),
                                        'book_name': book.get('book_name', t('dl_unknown_book')),
                                        'author': book.get('author', t('dl_unknown_author')),
                                        'abstract': book.get('abstract', '') or book.get('book_abstract_v2', t('dl_no_intro')),
                                        'cover_url': book.get('thumb_url', '') or book.get('cover', ''),
                                        'word_count': word_count,
                                        'chapter_count': chapter_count,
                                        'status': status,
                                        'category': book.get('category', '') or book.get('genre', '')
                                    })
                    break  # 找到书籍 tab 后退出
            
            return jsonify({
                'success': True,
                'data': {
                    'books': books,
                    'total': len(books),
                    'offset': offset,
                    'has_more': has_more
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'books': [],
                    'total': 0,
                    'offset': offset,
                    'has_more': False
                }
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': t('web_search_fail', str(e))}), 500

@app.route('/api/parse-chapter-range', methods=['POST'])
def api_parse_chapter_range():
    """解析章节范围字符串"""
    data = request.get_json() or {}
    input_str = data.get('input', '').strip()
    max_chapter = data.get('max_chapter', 0)
    
    if not input_str:
        return jsonify({
            'success': True,
            'data': {
                'chapters': [],
                'errors': [],
                'warnings': []
            }
        })
    
    try:
        max_chapter = int(max_chapter)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': '无效的最大章节数'}), 400
    
    result = ChapterRangeParser.parse(input_str, max_chapter)
    
    return jsonify({
        'success': result['success'],
        'data': {
            'chapters': result['chapters'],
            'errors': result['errors'],
            'warnings': result['warnings']
        }
    })


@app.route('/api/upload-book-list', methods=['POST'])
def api_upload_book_list():
    """上传并解析书籍列表文件"""
    # 检查是否有文件上传
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '未选择文件'}), 400
        
        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                file.seek(0)
                content = file.read().decode('gbk')
            except:
                return jsonify({'success': False, 'message': '文件编码不支持，请使用 UTF-8 或 GBK 编码'}), 400
    else:
        # 也支持直接传递文本内容
        data = request.get_json() or {}
        content = data.get('content', '')
    
    if not content:
        return jsonify({'success': False, 'message': '文件内容为空'}), 400
    
    result = BookListParser.parse_file_content(content)
    
    return jsonify({
        'success': True,
        'data': {
            'books': result['books'],
            'skipped': result['skipped'],
            'total_lines': result['total_lines'],
            'valid_count': len(result['books']),
            'skipped_count': len(result['skipped'])
        }
    })


# ===================== 下载历史 API =====================

@app.route('/api/download-history/check', methods=['POST'])
def api_download_history_check():
    """检查书籍是否已下载"""
    data = request.get_json() or {}
    book_id = data.get('book_id')
    book_ids = data.get('book_ids', [])
    
    history_manager = get_download_history_manager()
    
    # 单个检查
    if book_id:
        record = history_manager.check_exists(book_id)
        return jsonify({
            'success': True,
            'exists': record is not None,
            'record': record
        })
    
    # 批量检查
    if book_ids:
        results = history_manager.check_batch(book_ids)
        return jsonify({
            'success': True,
            'results': results
        })
    
    return jsonify({'success': False, 'message': '请提供 book_id 或 book_ids'}), 400


@app.route('/api/download-history/list', methods=['GET'])
def api_download_history_list():
    """获取下载历史列表"""
    history_manager = get_download_history_manager()
    records = history_manager.get_all_records()
    
    return jsonify({
        'success': True,
        'records': records,
        'total': len(records)
    })


@app.route('/api/download-history/add', methods=['POST'])
def api_download_history_add():
    """添加下载记录"""
    data = request.get_json() or {}
    
    required_fields = ['book_id', 'book_name', 'save_path', 'file_format']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'缺少必填字段: {field}'}), 400
    
    history_manager = get_download_history_manager()
    success = history_manager.add_record(
        book_id=data['book_id'],
        book_name=data['book_name'],
        author=data.get('author', ''),
        save_path=data['save_path'],
        file_format=data['file_format'],
        chapter_count=data.get('chapter_count', 0)
    )
    
    return jsonify({'success': success})


@app.route('/api/download-history/remove', methods=['POST'])
def api_download_history_remove():
    """删除下载记录"""
    data = request.get_json() or {}
    book_id = data.get('book_id')
    
    if not book_id:
        return jsonify({'success': False, 'message': '请提供 book_id'}), 400
    
    history_manager = get_download_history_manager()
    success = history_manager.remove_record(book_id)
    
    return jsonify({'success': success})


@app.route('/api/book-info', methods=['POST'])
def api_book_info():
    """获取书籍详情和章节列表"""
    print(f"[DEBUG] Received book-info request: {request.data}")
    data = request.get_json()
    book_id = data.get('book_id', '').strip()
    
    if not book_id:
        return jsonify({'success': False, 'message': t('web_book_id_empty')}), 400
    
    # 从URL中提取ID
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': t('web_url_error')}), 400
    
    # 验证book_id是数字
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': t('web_id_not_digit')}), 400
    
    if not api:
        return jsonify({'success': False, 'message': t('web_api_not_init')}), 500
    
    try:
        # 获取书籍信息
        print(f"[DEBUG] calling get_book_detail for {book_id}")
        book_detail = api_manager.get_book_detail(book_id)
        print(f"[DEBUG] book_detail result: {str(book_detail)[:100]}")
        if not book_detail:
            return jsonify({'success': False, 'message': t('web_book_info_fail')}), 400
        
        # 检查是否有错误（如书籍下架）
        if isinstance(book_detail, dict) and book_detail.get('_error'):
            error_type = book_detail.get('_error')
            if error_type == 'BOOK_REMOVE':
                return jsonify({'success': False, 'message': '该书籍已下架，无法下载'}), 400
            return jsonify({'success': False, 'message': f'获取书籍信息失败: {error_type}'}), 400
        
        # 获取章节列表
        print(f"[DEBUG] calling get_chapter_list for {book_id}")
        chapters_data = api_manager.get_chapter_list(book_id)
        print(f"[DEBUG] chapters_data type: {type(chapters_data)}")
        if not chapters_data:
            return jsonify({'success': False, 'message': t('web_chapter_list_fail')}), 400
        
        chapters = []
        if isinstance(chapters_data, dict):
            all_item_ids = chapters_data.get("allItemIds", [])
            chapter_list = chapters_data.get("chapterListWithVolume", [])
            
            if chapter_list:
                idx = 0
                for volume in chapter_list:
                    if isinstance(volume, list):
                        for ch in volume:
                            if isinstance(ch, dict):
                                item_id = ch.get("itemId") or ch.get("item_id")
                                title = ch.get("title", t("dl_chapter_title", idx+1))
                                if item_id:
                                    chapters.append({"id": str(item_id), "title": title, "index": idx})
                                    idx += 1
            else:
                for idx, item_id in enumerate(all_item_ids):
                    chapters.append({"id": str(item_id), "title": t("dl_chapter_title", idx+1), "index": idx})
        elif isinstance(chapters_data, list):
            for idx, ch in enumerate(chapters_data):
                item_id = ch.get("item_id") or ch.get("chapter_id")
                title = ch.get("title", t("dl_chapter_title", idx+1))
                if item_id:
                    chapters.append({"id": str(item_id), "title": title, "index": idx})
        
        print(f"[DEBUG] Found {len(chapters)} chapters")

        # 返回书籍信息和章节列表
        return jsonify({
            'success': True,
            'data': {
                'book_id': book_id,
                'book_name': book_detail.get('book_name', t('dl_unknown_book')),
                'author': book_detail.get('author', t('dl_unknown_author')),
                'abstract': book_detail.get('abstract', t('dl_no_intro')),
                'cover_url': book_detail.get('thumb_url', ''),
                'chapters': chapters
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': t('web_get_info_fail', str(e))}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    """开始下载"""
    data = request.get_json()
    
    if get_status()['is_downloading']:
        return jsonify({'success': False, 'message': t('web_download_exists')}), 400
    
    book_id = data.get('book_id', '').strip()
    save_path = data.get('save_path', get_default_download_path()).strip()
    file_format = data.get('file_format', 'txt')
    start_chapter = data.get('start_chapter')
    end_chapter = data.get('end_chapter')
    selected_chapters = data.get('selected_chapters')
    
    if not book_id:
        return jsonify({'success': False, 'message': t('web_book_id_empty')}), 400
    
    # 从URL中提取ID
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': t('web_url_error')}), 400
    
    # 验证book_id是数字
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': t('web_id_not_digit')}), 400
    
    # 确保路径存在
    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        return jsonify({'success': False, 'message': t('web_save_path_error', str(e))}), 400
    
    # 添加到下载队列
    task = {
        'book_id': book_id,
        'save_path': save_path,
        'file_format': file_format,
        'start_chapter': start_chapter,
        'end_chapter': end_chapter,
        'selected_chapters': selected_chapters
    }
    download_queue.put(task)
    update_status(is_downloading=True, progress=0, message=t('web_task_added'))
    
    return jsonify({'success': True, 'message': t('web_task_started')})


@app.route('/api/queue/start', methods=['POST'])
def api_queue_start():
    """提交待下载队列并开始下载（批量入队）"""
    data = request.get_json() or {}

    if get_status()['is_downloading']:
        return jsonify({'success': False, 'message': t('web_download_exists')}), 400

    tasks = data.get('tasks', [])
    save_path = str(data.get('save_path', get_default_download_path())).strip()
    file_format = str(data.get('file_format', 'txt')).strip().lower()

    if not tasks or not isinstance(tasks, list):
        return jsonify({'success': False, 'message': t('web_provide_ids')}), 400

    if file_format not in ['txt', 'epub']:
        file_format = 'txt'

    # 确保路径存在
    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        return jsonify({'success': False, 'message': t('web_save_path_error', str(e))}), 400

    # 清空旧队列（安全起见）
    try:
        while True:
            download_queue.get_nowait()
    except queue.Empty:
        pass

    cleaned_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            continue

        book_id = str(task.get('book_id', '')).strip()
        if not book_id:
            continue

        # 从URL中提取ID
        if 'fanqienovel.com' in book_id:
            match = re.search(r'/page/(\d+)', book_id)
            if match:
                book_id = match.group(1)
            else:
                continue

        if not book_id.isdigit():
            continue

        start_chapter = task.get('start_chapter')
        end_chapter = task.get('end_chapter')
        selected_chapters = task.get('selected_chapters')

        # 章节范围为 1-based（与下载器保持一致）
        try:
            if start_chapter is not None:
                start_chapter = int(start_chapter)
                if start_chapter <= 0:
                    start_chapter = None
            if end_chapter is not None:
                end_chapter = int(end_chapter)
                if end_chapter <= 0:
                    end_chapter = None
        except Exception:
            start_chapter = None
            end_chapter = None

        if selected_chapters is not None:
            try:
                if isinstance(selected_chapters, list):
                    selected_chapters = [int(x) for x in selected_chapters]
                else:
                    selected_chapters = None
            except Exception:
                selected_chapters = None

        cleaned_tasks.append({
            'book_id': book_id,
            'save_path': save_path,
            'file_format': file_format,
            'start_chapter': start_chapter,
            'end_chapter': end_chapter,
            'selected_chapters': selected_chapters
        })

    if not cleaned_tasks:
        return jsonify({'success': False, 'message': t('web_no_valid_ids')}), 400

    # 设置队列状态并批量入队
    update_status(
        is_downloading=True,
        progress=0,
        message=t('web_queue_submitted', len(cleaned_tasks)),
        book_name='',
        queue_total=len(cleaned_tasks),
        queue_done=0,
        queue_current=1
    )
    for task in cleaned_tasks:
        download_queue.put(task)

    return jsonify({'success': True, 'count': len(cleaned_tasks)})


@app.route('/api/queue/status', methods=['GET'])
def api_queue_status():
    """获取队列状态
    
    返回队列中所有任务的详细信息，包括状态、进度等
    """
    status = task_manager.get_queue_status()
    return jsonify({
        'success': True,
        'data': status
    })


@app.route('/api/queue/skip', methods=['POST'])
def api_queue_skip():
    """跳过当前任务
    
    停止当前书籍的下载并开始下载队列中的下一本书
    """
    result = task_manager.skip_current()
    if result:
        return jsonify({
            'success': True,
            'message': '已跳过当前任务'
        })
    else:
        return jsonify({
            'success': False,
            'message': '无法跳过：没有正在下载的任务'
        }), 400


@app.route('/api/queue/retry', methods=['POST'])
def api_queue_retry():
    """重试指定任务或所有失败任务
    
    请求体:
    - task_id: 指定任务ID（可选）
    - retry_all: 是否重试所有失败任务（可选）
    """
    data = request.get_json() or {}
    task_id = data.get('task_id')
    retry_all = data.get('retry_all', False)
    
    if retry_all:
        count = task_manager.retry_all_failed()
        if count > 0:
            return jsonify({
                'success': True,
                'message': f'已重置 {count} 个失败任务',
                'count': count
            })
        else:
            return jsonify({
                'success': False,
                'message': '没有失败的任务需要重试'
            }), 400
    elif task_id:
        result = task_manager.retry_task(task_id)
        if result:
            return jsonify({
                'success': True,
                'message': '任务已重置，等待重新下载'
            })
        else:
            return jsonify({
                'success': False,
                'message': '无法重试：任务不存在或状态不是失败'
            }), 400
    else:
        return jsonify({
            'success': False,
            'message': '请提供 task_id 或设置 retry_all=true'
        }), 400


@app.route('/api/queue/force-save', methods=['POST'])
def api_queue_force_save():
    """强制保存当前进度
    
    将当前已下载的章节内容保存到文件
    """
    result = task_manager.force_save()
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/download/resume-check', methods=['POST'])
def api_download_resume_check():
    """检查是否有可恢复的下载状态
    
    请求体:
    - book_id: 书籍ID
    
    返回:
    - has_saved_state: 是否有已保存的下载状态
    - downloaded_chapters: 已下载的章节数
    - total_chapters: 总章节数（如果已知）
    """
    data = request.get_json() or {}
    book_id = str(data.get('book_id', '')).strip()
    
    if not book_id:
        return jsonify({
            'success': False,
            'message': '请提供 book_id'
        }), 400
    
    # 从 novel_downloader 导入状态加载函数
    try:
        from novel_downloader import load_status, _get_status_file_path
        
        downloaded_ids = load_status(book_id)
        has_saved_state = len(downloaded_ids) > 0
        
        return jsonify({
            'success': True,
            'data': {
                'has_saved_state': has_saved_state,
                'downloaded_chapters': len(downloaded_ids),
                'book_id': book_id
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'检查下载状态失败: {str(e)}'
        }), 500


@app.route('/api/cancel', methods=['POST'])
def api_cancel():
    """取消下载"""
    if downloader_instance:
        try:
            downloader_instance.cancel_download()
            update_status(is_downloading=False, progress=0, message=t('web_batch_cancelled_msg'))
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400
    return jsonify({'success': False}), 400

# ===================== 批量下载状态 =====================
batch_download_status = {
    'is_downloading': False,
    'current_index': 0,
    'total_count': 0,
    'current_book': '',
    'results': [],
    'message': ''
}
batch_lock = threading.Lock()

def get_batch_status():
    """获取批量下载状态"""
    with batch_lock:
        return batch_download_status.copy()

def update_batch_status(**kwargs):
    """更新批量下载状态"""
    with batch_lock:
        for key, value in kwargs.items():
            if key in batch_download_status:
                batch_download_status[key] = value

def batch_download_worker(book_ids, save_path, file_format):
    """批量下载工作线程"""
    from novel_downloader import batch_downloader
    
    def progress_callback(current, total, book_name, status, message):
        update_batch_status(
            current_index=current,
            total_count=total,
            current_book=book_name,
            message=f'[{current}/{total}] {book_name}: {message}'
        )
    
    try:
        update_batch_status(
            is_downloading=True,
            current_index=0,
            total_count=len(book_ids),
            results=[],
            message='开始批量下载...'
        )
        
        result = batch_downloader.run_batch(
            book_ids, save_path, file_format,
            progress_callback=progress_callback,
            delay_between_books=2.0
        )
        
        update_batch_status(
            is_downloading=False,
            results=result.get('results', []),
            message=f"✅ 批量下载完成: {result['message']}"
        )
        
    except Exception as e:
        update_batch_status(
            is_downloading=False,
            message=f'❌ 批量下载失败: {str(e)}'
        )

@app.route('/api/batch-download', methods=['POST'])
def api_batch_download():
    """开始批量下载"""
    data = request.get_json()
    
    if get_batch_status()['is_downloading']:
        return jsonify({'success': False, 'message': t('web_batch_running')}), 400
    
    book_ids = data.get('book_ids', [])
    save_path = data.get('save_path', get_default_download_path()).strip()
    file_format = data.get('file_format', 'txt')
    
    if not book_ids:
        return jsonify({'success': False, 'message': t('web_provide_ids')}), 400
    
    # 清理和验证book_ids
    cleaned_ids = []
    for bid in book_ids:
        bid = str(bid).strip()
        # 从URL提取ID
        if 'fanqienovel.com' in bid:
            match = re.search(r'/page/(\d+)', bid)
            if match:
                bid = match.group(1)
        if bid.isdigit():
            cleaned_ids.append(bid)
    
    if not cleaned_ids:
        return jsonify({'success': False, 'message': t('web_no_valid_ids')}), 400
    
    # 确保保存目录存在
    os.makedirs(save_path, exist_ok=True)
    
    # 启动批量下载线程
    t = threading.Thread(
        target=batch_download_worker,
        args=(cleaned_ids, save_path, file_format),
        daemon=True
    )
    t.start()
    
    return jsonify({
        'success': True,
        'message': t('web_batch_start_count', len(cleaned_ids)),
        'count': len(cleaned_ids)
    })

@app.route('/api/batch-status', methods=['GET'])
def api_batch_status():
    """获取批量下载状态"""
    return jsonify(get_batch_status())

@app.route('/api/batch-cancel', methods=['POST'])
def api_batch_cancel():
    """取消批量下载"""
    from novel_downloader import batch_downloader
    
    try:
        batch_downloader.cancel()
        update_batch_status(
            is_downloading=False,
            message=t('web_batch_cancelled_msg')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/language', methods=['GET', 'POST'])
def api_language():
    """获取/设置语言配置"""
    from locales import get_current_lang, set_current_lang
    
    if request.method == 'GET':
        return jsonify({'language': get_current_lang()})
    else:
        data = request.get_json()
        lang = data.get('language', 'zh')
        if lang not in ['zh', 'en']:
            lang = 'zh'
        if set_current_lang(lang):
            return jsonify({'success': True, 'language': lang})
        else:
            return jsonify({'success': False, 'message': 'Failed to save language'}), 500

@app.route('/api/config/save-path', methods=['GET', 'POST'])
def api_config_save_path():
    """获取/保存下载路径配置"""
    
    if request.method == 'GET':
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return jsonify({'path': config.get('save_path', get_default_download_path())})
        except:
            pass
        return jsonify({'path': get_default_download_path()})
    
    else:
        data = request.get_json()
        path = data.get('path', get_default_download_path())
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            config['save_path'] = path
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/list-directory', methods=['POST'])
def api_list_directory():
    """列出指定目录的内容"""
    try:
        data = request.get_json() or {}
        path = data.get('path', '')
        
        # 如果没有指定路径，使用默认下载路径
        if not path:
            path = get_default_download_path()
        
        # 规范化路径
        path = os.path.normpath(os.path.expanduser(path))
    
        # 检查路径是否存在
        if not os.path.exists(path):
            return jsonify({
                'success': False,
                'message': '目录不存在'
            })
        
        # 检查是否是目录
        if not os.path.isdir(path):
            return jsonify({
                'success': False,
                'message': '路径不是目录'
            })
    
        # 获取目录列表
        directories = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                directories.append({
                    'name': item,
                    'path': item_path
                })
        
        # 按名称排序
        directories.sort(key=lambda x: x['name'].lower())
        
        # 获取父目录
        parent_path = os.path.dirname(path)
        is_root = (parent_path == path) or (path in ['/', '\\'])
        
        # Windows 驱动器列表
        drives = []
        if os.name == 'nt':
            import string
            for letter in string.ascii_uppercase:
                drive = f'{letter}:\\'
                if os.path.exists(drive):
                    drives.append({
                        'name': f'{letter}:',
                        'path': drive
                    })
        
        # 快捷路径（用户常用文件夹）
        quick_paths = []
        home = os.path.expanduser('~')
        
        # Windows 特殊文件夹
        if os.name == 'nt':
            shell_folders = [
                ('Desktop', 'Desktop', 'line-md:computer'),
                ('Downloads', 'Downloads', 'line-md:download-loop'),
                ('Documents', 'Documents', 'line-md:document'),
                ('Pictures', 'Pictures', 'line-md:image'),
                ('Music', 'Music', 'line-md:play'),
                ('Videos', 'Videos', 'line-md:play-filled'),
            ]
            for name, folder, icon in shell_folders:
                folder_path = os.path.join(home, folder)
                if os.path.exists(folder_path):
                    quick_paths.append({
                        'name': name,
                        'path': folder_path,
                        'icon': icon
                    })
        else:
            # Linux/macOS
            unix_folders = [
                ('Desktop', 'Desktop', 'line-md:computer'),
                ('Downloads', 'Downloads', 'line-md:download-loop'),
                ('Documents', 'Documents', 'line-md:document'),
                ('Pictures', 'Pictures', 'line-md:image'),
                ('Music', 'Music', 'line-md:play'),
                ('Videos', 'Videos', 'line-md:play-filled'),
            ]
            for name, folder, icon in unix_folders:
                folder_path = os.path.join(home, folder)
                if os.path.exists(folder_path):
                    quick_paths.append({
                        'name': name,
                        'path': folder_path,
                        'icon': icon
                    })
        
        return jsonify({
            'success': True,
            'data': {
                'current_path': path,
                'parent_path': parent_path if not is_root else None,
                'directories': directories,
                'is_root': is_root,
                'drives': drives if os.name == 'nt' else None,
                'quick_paths': quick_paths
            }
        })
    except PermissionError:
        return jsonify({
            'success': False,
            'message': '无权限访问该目录'
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] list-directory: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'加载目录失败: {str(e)}'
        })


@app.route('/api/select-folder', methods=['POST'])
def api_select_folder():
    """保存选择的文件夹路径"""
    data = request.get_json() or {}
    selected_path = data.get('path', '')
    
    if not selected_path:
        return jsonify({'success': False, 'message': '未选择文件夹'})
    
    # 验证路径存在且是目录
    if not os.path.exists(selected_path) or not os.path.isdir(selected_path):
        return jsonify({'success': False, 'message': '无效的目录路径'})
    
    # 保存选择的路径到配置
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        config['save_path'] = selected_path
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'path': selected_path})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/check-update', methods=['GET'])
def api_check_update():
    """检查更新"""
    try:
        import sys
        
        # 源代码运行时不检查更新
        if not getattr(sys, 'frozen', False):
            return jsonify({
                'success': True,
                'has_update': False,
                'is_source': True,
                'message': '源代码运行模式，不检查更新'
            })
        
        from updater import check_and_notify
        from config import __version__, __github_repo__
        
        update_info = check_and_notify(__version__, __github_repo__, silent=True)
        
        if update_info:
            return jsonify({
                'success': True,
                'has_update': update_info.get('has_update', False),
                'data': update_info
            })
        else:
            return jsonify({
                'success': True,
                'has_update': False
            })
    except Exception as e:
        return jsonify({'success': False, 'message': t('web_check_update_fail', str(e))}), 500

@app.route('/api/get-update-assets', methods=['GET'])
def api_get_update_assets():
    """获取更新文件的下载选项"""
    try:
        from updater import get_latest_release, parse_release_assets
        from config import __github_repo__
        import platform
        
        # 获取最新版本信息
        latest_info = get_latest_release(__github_repo__)
        if not latest_info:
            return jsonify({'success': False, 'message': '无法获取版本信息'}), 500
        
        # 检测当前平台
        system = platform.system().lower()
        if system == 'darwin':
            platform_name = 'macos'
        elif system == 'linux':
            platform_name = 'linux'
        else:
            platform_name = 'windows'
        
        # 解析 assets
        assets = parse_release_assets(latest_info, platform_name)
        
        return jsonify({
            'success': True,
            'platform': platform_name,
            'assets': assets,
            'release_url': latest_info.get('html_url', '')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取下载选项失败: {str(e)}'}), 500

@app.route('/api/download-update', methods=['POST'])
def api_download_update():
    """开始下载更新包"""
    data = request.get_json()
    url = data.get('url')
    filename = data.get('filename')
    
    if not url or not filename:
        return jsonify({'success': False, 'message': '参数错误'}), 400
        
    # 使用默认下载路径或配置路径
    save_path = get_default_download_path()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                save_path = config.get('save_path', save_path)
        except:
            pass
            
    if not os.path.exists(save_path):
        try:
            os.makedirs(save_path)
        except:
            save_path = get_default_download_path()

    # 启动下载线程
    t = threading.Thread(
        target=update_download_worker, 
        args=(url, save_path, filename),
        daemon=True
    )
    t.start()
    
    return jsonify({'success': True, 'message': '开始下载'})

@app.route('/api/update-status', methods=['GET'])
def api_get_update_status_route():
    """获取更新下载状态"""
    return jsonify(get_update_status())

@app.route('/api/can-auto-update', methods=['GET'])
def api_can_auto_update():
    """检查是否支持自动更新"""
    try:
        from updater import can_auto_update
        return jsonify({
            'success': True,
            'can_auto_update': can_auto_update()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/apply-update', methods=['POST'])
def api_apply_update():
    """应用已下载的更新（支持 Windows/Linux/macOS）"""
    print('[DEBUG] api_apply_update called')
    try:
        from updater import apply_update, can_auto_update
        import sys
        
        print(f'[DEBUG] sys.frozen: {getattr(sys, "frozen", False)}')
        print(f'[DEBUG] sys.executable: {sys.executable}')
        
        # 检查是否支持自动更新
        can_update = can_auto_update()
        print(f'[DEBUG] can_auto_update: {can_update}')
        if not can_update:
            return jsonify({
                'success': False, 
                'message': t('web_auto_update_unsupported')
            }), 400
        
        # 获取下载的更新文件信息
        status = get_update_status()
        print(f'[DEBUG] update_status: {status}')
        if not status.get('completed'):
            return jsonify({
                'success': False, 
                'message': t('web_update_not_ready')
            }), 400
        
        # 使用临时文件路径
        new_file_path = status.get('temp_file_path', '')
        print(f'[DEBUG] temp_file_path: {new_file_path}')
        
        print(f'[DEBUG] new_file_path: {new_file_path}')
        
        if not new_file_path:
            return jsonify({
                'success': False, 
                'message': t('web_update_info_incomplete')
            }), 400
        
        print(f'[DEBUG] file exists: {os.path.exists(new_file_path)}')
        
        if not os.path.exists(new_file_path):
            return jsonify({
                'success': False, 
                'message': t('web_update_file_missing', new_file_path)
            }), 400
        
        print(f'[DEBUG] file size: {os.path.getsize(new_file_path)} bytes')
        
        # 应用更新（自动检测平台）
        print('[DEBUG] Calling apply_update...')
        if apply_update(new_file_path):
            # 更新成功启动，准备退出程序
            # 等待足够时间确保更新脚本已启动并开始监控进程
            def delayed_exit():
                import time
                print('[DEBUG] Waiting for update script to start...')
                time.sleep(3)  # 给更新脚本足够的启动时间
                print('[DEBUG] Exiting application for update...')
                os._exit(0)
            
            # 使用非守护线程确保退出逻辑能完成
            exit_thread = threading.Thread(target=delayed_exit, daemon=False)
            exit_thread.start()
            
            return jsonify({
                'success': True, 
                'message': t('web_update_start_success')
            })
        else:
            return jsonify({
                'success': False, 
                'message': t('web_update_start_fail')
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': t('web_apply_update_fail', str(e))}), 500

@app.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    """打开文件夹"""
    data = request.get_json()
    path = data.get('path')
    
    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'message': t('web_path_not_exist')}), 400
        
    try:
        if os.name == 'nt':
            os.startfile(path)
        elif os.name == 'posix':
            subprocess.call(['open', path])
        else:
            subprocess.call(['xdg-open', path])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print(f'配置文件位置: {CONFIG_FILE}')
    print(t('web_server_started'))
    app.run(host='127.0.0.1', port=5000, debug=False)
