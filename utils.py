# -*- coding: utf-8 -*-
"""
工具模块 - 包含共享的工具函数
"""

import os
import json
import re
import time
import requests
from typing import Optional, Dict, List
from ebooklib import epub
from config import CONFIG, print_lock, get_headers
from watermark import apply_watermark_to_chapter


def parse_chapters_list(chapters_data) -> List[Dict]:
    """
    解析章节列表数据，支持多种格式
    
    Args:
        chapters_data: API返回的章节数据
    
    Returns:
        标准格式的章节列表 [{"id": str, "title": str, "index": int}, ...]
    """
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
                            title = ch.get("title", f"第{idx+1}章")
                            if item_id:
                                chapters.append({"id": str(item_id), "title": title, "index": idx})
                                idx += 1
        else:
            for idx, item_id in enumerate(all_item_ids):
                chapters.append({"id": str(item_id), "title": f"第{idx+1}章", "index": idx})
    elif isinstance(chapters_data, list):
        for idx, ch in enumerate(chapters_data):
            item_id = ch.get("item_id") or ch.get("chapter_id")
            title = ch.get("title", f"第{idx+1}章")
            if item_id:
                chapters.append({"id": str(item_id), "title": title, "index": idx})
    
    return chapters


def process_chapter_content(content):
    """处理章节内容"""
    if not content:
        return ""
    
    # 将br标签和p标签替换为换行符
    content = re.sub(r'<br\s*/?>\s*', '\n', content)
    content = re.sub(r'<p[^>]*>\s*', '\n', content)
    content = re.sub(r'</p>\s*', '\n', content)
    
    # 移除其他HTML标签
    content = re.sub(r'<[^>]+>', '', content)
    
    # 清理空白字符
    content = re.sub(r'[ \t]+', ' ', content)  # 多个空格或制表符替换为单个空格
    content = re.sub(r'\n[ \t]+', '\n', content)  # 行首空白
    content = re.sub(r'[ \t]+\n', '\n', content)  # 行尾空白
    
    # 将多个连续换行符规范化为双换行（段落分隔）
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # 处理段落：确保每个非空行都是一个段落
    lines = content.split('\n')
    paragraphs = []
    for line in lines:
        line = line.strip()
        if line:  # 非空行
            paragraphs.append(line)
    
    # 用双换行符连接段落
    content = '\n\n'.join(paragraphs)
    
    # 应用水印处理
    content = apply_watermark_to_chapter(content)
    
    return content


def load_status(save_path):
    """加载下载状态"""
    status_file = os.path.join(save_path, CONFIG.get("status_file", ".download_status.json"))
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except:
            pass
    return set()


def save_status(save_path, downloaded_ids):
    """保存下载状态"""
    status_file = os.path.join(save_path, CONFIG.get("status_file", ".download_status.json"))
    try:
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(list(downloaded_ids), f, ensure_ascii=False, indent=2)
    except Exception as e:
        with print_lock:
            print(f"保存下载状态失败: {str(e)}")


def download_cover(cover_url, headers):
    """下载封面图片"""
    if not cover_url:
        return None, None, None
    
    try:
        response = requests.get(cover_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None, None, None
        
        content_type = response.headers.get('content-type', '')
        content_bytes = response.content
        
        if len(content_bytes) < 1000:
            return None, None, None
        
        if 'jpeg' in content_type or 'jpg' in content_type:
            file_ext, mime_type = '.jpg', 'image/jpeg'
        elif 'png' in content_type:
            file_ext, mime_type = '.png', 'image/png'
        elif 'webp' in content_type:
            file_ext, mime_type = '.webp', 'image/webp'
        else:
            file_ext, mime_type = '.jpg', 'image/jpeg'
        
        return content_bytes, file_ext, mime_type
        
    except Exception as e:
        with print_lock:
            print(f"下载封面失败: {str(e)}")
        return None, None, None


def create_epub(name, author_name, description, cover_url, chapters, save_path):
    """创建EPUB文件"""
    book = epub.EpubBook()
    book.set_identifier(f'fanqie_{int(time.time())}')
    book.set_title(name)
    book.set_language('zh-CN')
    
    if author_name:
        book.add_author(author_name)
    
    if description:
        book.add_metadata('DC', 'description', description)
    
    if cover_url:
        try:
            cover_content, file_ext, mime_type = download_cover(cover_url, get_headers())
            if cover_content and file_ext and mime_type:
                book.set_cover(f'cover{file_ext}', cover_content)
        except Exception as e:
            with print_lock:
                print(f"添加封面失败: {str(e)}")
    
    spine_items = ['nav']
    toc_items = []
    
    for idx, ch_data in enumerate(chapters):
        chapter_file = f'chapter_{idx + 1}.xhtml'
        title = ch_data.get('title', f'第{idx + 1}章')
        content = ch_data.get('content', '')
        
        # 将换行符转换为HTML段落标签
        paragraphs = content.split('\n\n') if content else []
        html_paragraphs = ''.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())
        
        chapter = epub.EpubHtml(
            title=title,
            file_name=chapter_file,
            lang='zh-CN'
        )
        chapter.content = f'<h1>{title}</h1><div>{html_paragraphs}</div>'
        
        book.add_item(chapter)
        spine_items.append(chapter)
        toc_items.append(chapter)
    
    book.toc = toc_items
    book.spine = spine_items
    
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    filename = re.sub(r'[\\/:*?"<>|]', '_', name)
    epub_path = os.path.join(save_path, f'{filename}.epub')
    epub.write_epub(epub_path, book)
    
    return epub_path


def create_txt(name, author_name, description, chapters, save_path):
    """创建TXT文件"""
    filename = re.sub(r'[\\/:*?"<>|]', '_', name)
    txt_path = os.path.join(save_path, f'{filename}.txt')
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"{name}\n")
        if author_name:
            f.write(f"作者: {author_name}\n")
        if description:
            f.write(f"\n简介:\n{description}\n")
        f.write("\n" + "="*50 + "\n\n")
        
        for ch_data in chapters:
            title = ch_data.get('title', '')
            content = ch_data.get('content', '')
            f.write(f"\n{title}\n\n")
            f.write(f"{content}\n\n")
    
    return txt_path
