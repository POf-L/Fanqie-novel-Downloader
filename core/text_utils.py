# -*- coding: utf-8 -*-
"""小说文本与文件名处理工具。"""

import re
from typing import Dict, List, Optional


def normalize_title(title: str) -> str:
    """标准化章节标题，用于模糊匹配。"""
    s = re.sub(r'\s+', '', title)
    s = re.sub(r'[,，、．.·]', '', s)
    return s.lower()


def extract_title_core(title: str) -> str:
    """提取标题核心部分（去掉章节号前缀）。"""
    s = re.sub(r'^(第[0-9一二三四五六七八九十百千]+章[、,，\s]*)', '', title)
    s = re.sub(r'^(\d+[、,，.\s]+)', '', s)
    return s.strip()


def parse_novel_text_with_catalog(text: str, catalog: List[Dict]) -> List[Dict]:
    """使用目录章节标题分割整本小说内容。"""
    if not catalog:
        return []

    def find_title_in_text(title: str, search_text: str, start_offset: int = 0) -> Optional[tuple]:
        pattern = re.compile(r'^[ \t]*' + re.escape(title) + r'[ \t]*$', re.MULTILINE)
        match = pattern.search(search_text)
        if match:
            return (start_offset + match.start(), start_offset + match.end())

        title_core = extract_title_core(title)
        if title_core and len(title_core) >= 2:
            pattern = re.compile(r'^[^\n]*' + re.escape(title_core) + r'[^\n]*$', re.MULTILINE)
            match = pattern.search(search_text)
            if match:
                return (start_offset + match.start(), start_offset + match.end())
        return None

    chapter_positions = []
    for ch in catalog:
        title = ch['title']
        result = find_title_in_text(title, text)
        if result:
            chapter_positions.append({
                'title': title,
                'id': ch.get('id', ''),
                'index': ch['index'],
                'line_start': result[0],
                'start': result[1]
            })

    if not chapter_positions:
        return []

    chapter_positions.sort(key=lambda x: x['line_start'])
    chapters = []
    for i, pos in enumerate(chapter_positions):
        end = chapter_positions[i + 1]['line_start'] if i + 1 < len(chapter_positions) else len(text)
        content = text[pos['start']:end].strip()
        chapters.append({
            'title': pos['title'],
            'id': pos['id'],
            'index': pos['index'],
            'content': content
        })

    chapters.sort(key=lambda x: x['index'])
    return chapters


def parse_novel_text(text: str) -> List[Dict]:
    """解析整本小说文本，分离章节（无目录时降级）。"""
    lines = text.splitlines()
    chapters = []
    current_chapter = None
    current_content = []

    chapter_pattern = re.compile(
        r'^\s*('
        r'第[0-9一二三四五六七八九十百千]+章'
        r'|[0-9]+[\.、,，]\s*\S'
        r')\s*.*',
        re.UNICODE
    )

    for line in lines:
        match = chapter_pattern.match(line)
        if match:
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content)
                chapters.append(current_chapter)

            current_chapter = {
                'title': line.strip(),
                'id': str(len(chapters)),
                'index': len(chapters)
            }
            current_content = []
        elif current_chapter:
            current_content.append(line)

    if current_chapter:
        current_chapter['content'] = '\n'.join(current_content)
        chapters.append(current_chapter)

    return chapters


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符。"""
    if not name:
        return ""
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def generate_filename(book_name: str, author_name: str, extension: str) -> str:
    """生成书籍输出文件名。"""
    safe_book_name = sanitize_filename(book_name)
    safe_author_name = sanitize_filename(author_name) if author_name else ""
    ext = extension.lstrip('.')
    if safe_author_name and safe_author_name.strip():
        return f"{safe_book_name} 作者：{safe_author_name}.{ext}"
    return f"{safe_book_name}.{ext}"


def process_chapter_content(content, watermark_func=None):
    """清洗章节内容并可选应用水印。"""
    if not content:
        return ""

    content = re.sub(r'<br\s*/?>\s*', '\n', content)
    content = re.sub(r'<p[^>]*>\s*', '\n', content)
    content = re.sub(r'</p>\s*', '\n', content)
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'[ \t]+', ' ', content)
    content = re.sub(r'\n[ \t]+', '\n', content)
    content = re.sub(r'[ \t]+\n', '\n', content)
    content = re.sub(r'\n{3,}', '\n\n', content)

    paragraphs = []
    for line in content.split('\n'):
        line = line.strip()
        if line:
            paragraphs.append(line)
    content = '\n\n'.join(paragraphs)

    if watermark_func:
        content = watermark_func(content)
    return content
