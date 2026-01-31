# -*- coding: utf-8 -*-
"""
文件工具 - 文件名处理、文件创建等
"""

import os
import re
import time
import requests
from ebooklib import epub

from config.config import CONFIG, print_lock, get_headers
from utils.watermark import apply_watermark_to_chapter


# 文件系统非法字符
ILLEGAL_FILENAME_CHARS = r'\/:*?"<>|'


def sanitize_filename(name: str) -> str:
    r"""
    清理文件名中的非法字符
    
    Args:
        name: 原始文件名
    
    Returns:
        清理后的文件名，非法字符 (\ / : * ? " < > |) 替换为下划线
    """
    if not name:
        return ""
    # 将非法字符替换为下划线
    result = re.sub(r'[\\/:*?"<>|]', '_', name)
    return result


def generate_filename(book_name: str, author_name: str, extension: str) -> str:
    """
    生成文件名
    
    Args:
        book_name: 书名
        author_name: 作者名 (可为空)
        extension: 文件扩展名 (txt/epub)
    
    Returns:
        格式化的文件名: "{书名} 作者：{作者名}.{扩展名}" 或 "{书名}.{扩展名}"
    """
    # 清理书名和作者名中的非法字符
    safe_book_name = sanitize_filename(book_name)
    safe_author_name = sanitize_filename(author_name) if author_name else ""
    
    # 确保扩展名不以点开头
    ext = extension.lstrip('.')
    
    # 根据作者名是否为空生成不同格式的文件名
    if safe_author_name and safe_author_name.strip():
        return f"{safe_book_name} 作者：{safe_author_name}.{ext}"
    else:
        return f"{safe_book_name}.{ext}"


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
    
    # 创建书籍信息页 (简介页)
    intro_html = f'<h1>{name}</h1>'
    if author_name:
        intro_html += f'<p><strong>作者：</strong> {author_name}</p>'
    
    if description:
        intro_html += '<hr/>'
        intro_html += f'<h3>简介</h3>'
        # 处理简介的换行
        desc_lines = description.split('\n')
        for line in desc_lines:
            if line.strip():
                intro_html += f'<p>{line.strip()}</p>'
                
    intro_chapter = epub.EpubHtml(title='书籍详情', file_name='intro.xhtml', lang='zh-CN')
    intro_chapter.content = intro_html
    book.add_item(intro_chapter)
    
    # 将简介页添加到 spine 和 toc
    spine_items.append(intro_chapter)
    toc_items.append(intro_chapter)

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
    
    # 使用新的文件命名逻辑
    filename = generate_filename(name, author_name, 'epub')
    epub_path = os.path.join(save_path, filename)
    epub.write_epub(epub_path, book)
    
    return epub_path


def create_txt(name, author_name, description, chapters, save_path):
    """创建TXT文件"""
    # 使用新的文件命名逻辑
    filename = generate_filename(name, author_name, 'txt')
    txt_path = os.path.join(save_path, filename)
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"{name}\n")
        if author_name:
            f.write(f"作者：{author_name}\n")
        if description:
            f.write(f"\n简介:\n{description}\n")
        f.write("\n" + "="*50 + "\n\n")
        
        for ch_data in chapters:
            title = ch_data.get('title', '')
            content = ch_data.get('content', '')
            f.write(f"\n{title}\n\n")
            f.write(f"{content}\n\n")
    
    return txt_path
