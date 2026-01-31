# -*- coding: utf-8 -*-
"""
文本解析器 - 处理小说文本解析和章节分割
"""

import re
from typing import Optional, List, Dict


def _normalize_title(title: str) -> str:
    """标准化章节标题，用于模糊匹配"""
    # 移除空格
    s = re.sub(r'\s+', '', title)
    # 统一标点：中文逗号、顿号、点号统一
    s = re.sub(r'[,，、．.·]', '', s)
    # 阿拉伯数字转中文数字的映射（用于比较）
    return s.lower()


def _extract_title_core(title: str) -> str:
    """提取标题核心部分（去掉章节号前缀）"""
    # 移除 "第x章"、"数字、"、"数字." 等前缀
    s = re.sub(r'^(第[0-9一二三四五六七八九十百千]+章[、,，\s]*)', '', title)
    s = re.sub(r'^(\d+[、,，.\s]+)', '', s)
    return s.strip()


def parse_novel_text_with_catalog(text: str, catalog: List[Dict]) -> List[Dict]:
    """使用目录接口的章节标题来分割整本小说内容
    
    Args:
        text: 整本小说的纯文本内容
        catalog: 目录接口返回的章节列表 [{'title': '...', 'id': '...', 'index': ...}, ...]
    
    Returns:
        带内容的章节列表 [{'title': '...', 'id': '...', 'index': ..., 'content': '...'}, ...]
    """
    if not catalog:
        return []
    
    def escape_for_regex(s: str) -> str:
        return re.escape(s)
    
    def find_title_in_text(title: str, search_text: str, start_offset: int = 0) -> Optional[tuple]:
        """在文本中查找标题，返回 (match_start, match_end) 或 None"""
        # 1. 精确匹配
        pattern = re.compile(r'^[ \t]*' + escape_for_regex(title) + r'[ \t]*$', re.MULTILINE)
        match = pattern.search(search_text)
        if match:
            return (start_offset + match.start(), start_offset + match.end())
        
        # 2. 模糊匹配：提取标题核心部分
        title_core = _extract_title_core(title)
        if title_core and len(title_core) >= 2:
            # 匹配包含核心标题的行
            pattern = re.compile(r'^[^\n]*' + escape_for_regex(title_core) + r'[^\n]*$', re.MULTILINE)
            match = pattern.search(search_text)
            if match:
                return (start_offset + match.start(), start_offset + match.end())
        
        return None
    
    # 查找每个章节标题在文本中的位置
    chapter_positions = []
    for ch in catalog:
        title = ch['title']
        result = find_title_in_text(title, text)
        if result:
            chapter_positions.append({
                'title': title,
                'id': ch.get('id', ''),
                'index': ch['index'],
                'line_start': result[0],  # 标题行开始位置
                'start': result[1]        # 内容开始位置（标题行之后）
            })
    
    if not chapter_positions:
        return []
    
    # 按位置排序
    chapter_positions.sort(key=lambda x: x['line_start'])
    
    # 提取每章内容
    chapters = []
    for i, pos in enumerate(chapter_positions):
        if i + 1 < len(chapter_positions):
            end = chapter_positions[i + 1]['line_start']
        else:
            end = len(text)
        
        content = text[pos['start']:end].strip()
        chapters.append({
            'title': pos['title'],
            'id': pos['id'],
            'index': pos['index'],
            'content': content
        })
    
    # 按原始目录顺序重新排序
    chapters.sort(key=lambda x: x['index'])
    
    return chapters


def parse_novel_text(text: str) -> List[Dict]:
    """解析整本小说文本，分离章节（无目录时的降级方案）"""
    lines = text.splitlines()
    chapters = []
    
    current_chapter = None
    current_content = []
    
    # 匹配常见章节格式
    chapter_pattern = re.compile(
        r'^\s*('
        r'第[0-9一二三四五六七八九十百千]+章'  # 第x章
        r'|[0-9]+[\.、,，]\s*\S'                # 1、标题 1.标题
        r')\s*.*',
        re.UNICODE
    )
    
    for line in lines:
        match = chapter_pattern.match(line)
        if match:
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content)
                chapters.append(current_chapter)
            
            title = line.strip()
            current_chapter = {
                'title': title,
                'id': str(len(chapters)),
                'index': len(chapters)
            }
            current_content = []
        else:
            if current_chapter:
                current_content.append(line)
    
    if current_chapter:
        current_chapter['content'] = '\n'.join(current_content)
        chapters.append(current_chapter)
    
    return chapters
