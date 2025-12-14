# -*- coding: utf-8 -*-
"""
水印处理模块 - 在下载的小说内容中插入水印和隐形字符
"""

import random
from locales import t

# 隐形字符列表 (仅保留不影响阅读顺序的字符)
INVISIBLE_CHARS = [
    '\u200B',  # 零宽空格 Zero-width space
    '\u200C',  # 零宽非连接符 Zero-width non-joiner
    '\u200D',  # 零宽连接符 Zero-width joiner
    '\uFEFF',  # 零宽不换行空格 Zero-width no-break space
]


def add_invisible_chars_to_text(text: str, insertion_rate: float = 0.3) -> str:
    """
    在文本的每个字符后面随机插入隐形字符
    
    Args:
        text: 输入文本
        insertion_rate: 隐形字符插入率 (0-1)，表示有多少比例的字符后面会插入隐形字符
    
    Returns:
        包含隐形字符的文本
    """
    if not text:
        return text
    
    result = []
    for char in text:
        result.append(char)
        # 随机决定是否插入隐形字符
        if random.random() < insertion_rate:
            # 随机选择一个隐形字符
            invisible_char = random.choice(INVISIBLE_CHARS)
            result.append(invisible_char)
    
    return ''.join(result)


def apply_watermark_to_chapter(content: str) -> str:
    """
    为章节内容应用完整的水印处理（在章节末尾添加水印 + 隐形字符）
    
    Args:
        content: 章节内容
    
    Returns:
        处理后的内容
    """
    if not content:
        return content
    
    # 默认水印文本
    watermark_text = t("wm_watermark_simple")
    
    # 将水印文本添加隐形字符
    watermarked_text = add_invisible_chars_to_text(watermark_text, insertion_rate=0.25)
    
    # 在章节末尾添加水印（使用双换行分隔）
    content = content + '\n\n' + watermarked_text
    
    return content
