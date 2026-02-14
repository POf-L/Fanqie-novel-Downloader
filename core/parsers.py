# -*- coding: utf-8 -*-
import os
import json

from utils.book_id import extract_book_id_with_min_length


class BookListParser:
    """解析书籍列表文件
    
    支持格式：
    - 纯书籍ID: 12345
    - 完整URL: https://fanqienovel.com/page/12345
    - 注释行: # 这是注释
    - 空行会被忽略
    """
    
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
        return extract_book_id_with_min_length(line, min_length=5)


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
                except Exception:
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
