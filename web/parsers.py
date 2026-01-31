# -*- coding: utf-8 -*-
"""
解析器模块 - 书籍列表和章节范围解析
"""

import re


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


class ChapterRangeParser:
    """章节范围解析器
    
    支持格式：
    - 单个章节: 5
    - 范围: 1-10
    - 多个范围: 1-10, 20-30
    - 混合: 1-10, 15, 20-25
    """
    
    @staticmethod
    def parse(input_str: str, max_chapter: int = 0) -> dict:
        """
        解析章节范围字符串
        
        Args:
            input_str: 输入字符串
            max_chapter: 最大章节数（用于验证）
        
        Returns:
            {
                'success': bool,
                'chapters': List[int],  # 章节索引列表（0-based）
                'errors': List[str],     # 错误信息
                'warnings': List[str]   # 警告信息
            }
        """
        result = {
            'success': True,
            'chapters': [],
            'errors': [],
            'warnings': []
        }
        
        if not input_str or not input_str.strip():
            return result
        
        # 分割输入（支持逗号、分号、空格等分隔符）
        parts = re.split(r'[,;\s]+', input_str.strip())
        
        for part in parts:
            if not part:
                continue
            
            # 检查是否为范围（如 1-10）
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    if start > end:
                        result['errors'].append(f"无效范围: {part} (起始大于结束)")
                        result['success'] = False
                    else:
                        # 转换为0-based索引
                        start_idx = start - 1
                        end_idx = end - 1
                        result['chapters'].extend(range(start_idx, end_idx + 1))
                except ValueError:
                    result['errors'].append(f"无效范围格式: {part}")
                    result['success'] = False
            else:
                # 单个章节
                try:
                    chapter = int(part)
                    # 转换为0-based索引
                    result['chapters'].append(chapter - 1)
                except ValueError:
                    result['errors'].append(f"无效章节: {part}")
                    result['success'] = False
        
        # 去重并排序
        result['chapters'] = sorted(list(set(result['chapters'])))
        
        # 验证章节范围
        if max_chapter > 0:
            invalid_chapters = [c for c in result['chapters'] if c >= max_chapter]
            if invalid_chapters:
                result['warnings'].append(
                    f"以下章节超出范围（共{max_chapter}章）: {', '.join(str(c+1) for c in invalid_chapters[:5])}"
                )
                # 移除无效章节
                result['chapters'] = [c for c in result['chapters'] if c < max_chapter]
        
        return result
