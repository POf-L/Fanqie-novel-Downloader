# -*- coding: utf-8 -*-
"""
水印处理模块 - 在下载的小说内容中插入水印和隐形字符
"""

import random
import re

# 隐形字符列表
INVISIBLE_CHARS = [
    '\u200B',  # 零宽空格 Zero-width space
    '\u200C',  # 零宽非连接符 Zero-width non-joiner
    '\u200D',  # 零宽连接符 Zero-width joiner
    '\u200E',  # 左至右符号 Left-to-right mark
    '\u200F',  # 右至左符号 Right-to-left mark
    '\u202A',  # 左至右嵌入 Left-to-right embedding
    '\u202B',  # 右至左嵌入 Right-to-left embedding
    '\u202C',  # 弹出方向格式 Pop directional formatting
    '\u202D',  # 左至右覆盖 Left-to-right override
    '\u202E',  # 右至左覆盖 Right-to-left override
    '\u061C',  # 阿拉伯字母标记 Arabic letter mark
    '\uFEFF',  # 零宽不换行空格 Zero-width no-break space
    '\u00AD',  # 软连字符 Soft hyphen
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


def insert_watermark(content: str, watermark_text: str = None, num_insertions: int = None) -> str:
    """
    在内容中随机多个位置插入带有隐形字符的水印文本
    
    Args:
        content: 原始内容
        watermark_text: 水印文本，默认为官方水印文本
        num_insertions: 插入次数，如果为None则根据内容长度自动计算
    
    Returns:
        包含水印的内容
    """
    if not content:
        return content
    
    # 默认水印文本
    if watermark_text is None:
        watermark_text = "当前小说使用https://github.com/POf-L/Fanqie-novel-Downloader免费下载器下载，购买的请立即差评并申请退款和举报！"
    
    # 自动计算插入次数
    if num_insertions is None:
        # 根据内容长度计算，大约每5000字插入一次
        num_insertions = max(1, len(content) // 5000 + random.randint(0, 2))
    
    # 将水印文本添加隐形字符
    watermarked_text = add_invisible_chars_to_text(watermark_text, insertion_rate=0.25)
    
    # 获取所有可用的插入位置（段落之间）
    paragraphs = content.split('\n\n')
    
    if len(paragraphs) <= 1:
        # 如果没有足够的段落分隔，直接在内容中随机插入
        insertion_positions = []
        sentences = re.split(r'([。！？])', content)
        
        cumulative_pos = 0
        for i, sentence in enumerate(sentences):
            if sentence and sentence not in '。！？':
                insertion_positions.append(cumulative_pos + len(sentence))
            cumulative_pos += len(sentence)
        
        # 随机选择插入位置
        if insertion_positions:
            num_insertions = min(num_insertions, len(insertion_positions))
            selected_positions = sorted(random.sample(insertion_positions, num_insertions), reverse=True)
            
            for pos in selected_positions:
                content = content[:pos] + '\n\n' + watermarked_text + '\n\n' + content[pos:]
        else:
            content = content + '\n\n' + watermarked_text
    else:
        # 在段落之间随机插入水印
        num_insertions = min(num_insertions, len(paragraphs) - 1)
        insertion_indices = sorted(random.sample(range(1, len(paragraphs)), num_insertions), reverse=True)
        
        for idx in insertion_indices:
            paragraphs.insert(idx, watermarked_text)
        
        content = '\n\n'.join(paragraphs)
    
    return content


def apply_watermark_to_chapter(content: str) -> str:
    """
    为章节内容应用完整的水印处理（水印插入 + 隐形字符）
    
    Args:
        content: 章节内容
    
    Returns:
        处理后的内容
    """
    if not content:
        return content
    
    # 首先插入水印文本
    content = insert_watermark(content)
    
    # 然后在整个内容中添加隐形字符
    content = add_invisible_chars_to_text(content, insertion_rate=0.15)
    
    return content
