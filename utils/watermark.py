# -*- coding: utf-8 -*-
"""
水印处理模块 - 增强版（仅章节末尾 + 强防护，保持URL可点击性）
"""

import random
import re
import hashlib
import time

# 扩展隐形字符集（这些字符不会影响URL识别）
ENHANCED_INVISIBLE_CHARS = [
    '\u200B',  # 零宽空格 Zero-width space
    '\u200C',  # 零宽非连接符 Zero-width non-joiner
    '\u200D',  # 零宽连接符 Zero-width joiner
    '\uFEFF',  # 零宽不换行空格 Zero-width no-break space
    '\u2060',  # 词连接符 Word joiner
    '\u180E',  # 蒙古文元音分隔符 Mongolian vowel separator
    '\u061C',  # 阿拉伯字母标记 Arabic letter mark
    '\u200E',  # 从左到右标记 Left-to-right mark
    '\u200F',  # 从右到左标记 Right-to-left mark
]

# 保持向后兼容的原始隐形字符列表
INVISIBLE_CHARS = [
    '\u200B',  # 零宽空格 Zero-width space
    '\u200C',  # 零宽非连接符 Zero-width non-joiner
    '\u200D',  # 零宽连接符 Zero-width joiner
    '\uFEFF',  # 零宽不换行空格 Zero-width no-break space
]


def generate_random_invisible_sequence(min_len: int, max_len: int) -> str:
    """生成随机长度的隐形字符序列"""
    length = random.randint(min_len, max_len)
    return ''.join(random.choice(ENHANCED_INVISIBLE_CHARS) for _ in range(length))


def add_enhanced_invisible_chars(text: str) -> str:
    """
    增强版隐形字符插入 - 仅使用隐形字符，保持URL可点击性
    """
    result = []
    for i, char in enumerate(text):
        result.append(char)

        # 智能插入概率 - 在不影响URL识别的位置插入
        insertion_rate = 0.4  # 基础概率
        if char in '/.:-':
            insertion_rate = 0.6  # 分隔符后适度增加
        elif char in 'aeiouAEIOU':
            insertion_rate = 0.3  # 元音后降低概率
        elif char.isdigit():
            insertion_rate = 0.4  # 数字后保持基础概率

        if random.random() < insertion_rate:
            # 随机选择1-2个隐形字符
            num_chars = random.randint(1, 2)
            for _ in range(num_chars):
                invisible_char = random.choice(ENHANCED_INVISIBLE_CHARS)
                result.append(invisible_char)

    return ''.join(result)


def embed_content_fingerprint(content: str) -> str:
    """基于内容特征嵌入指纹"""
    # 计算内容哈希
    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]

    # 将哈希值转换为隐形字符序列
    char_map = {
        '0': '\u200B', '1': '\u200C', '2': '\u200D', '3': '\uFEFF',
        '4': '\u2060', '5': '\u180E', '6': '\u061C', '7': '\u200E',
        '8': '\u200F', '9': '\u202A', 'a': '\u202B', 'b': '\u202C',
        'c': '\u202D', 'd': '\u202E', 'e': '\u2066', 'f': '\u2067'
    }

    fingerprint = ''.join(char_map.get(c, '\u200B') for c in content_hash)
    return fingerprint


def add_timestamp_watermark() -> str:
    """添加时间戳隐形水印"""
    timestamp = str(int(time.time()))[-6:]  # 取后6位

    # 将时间戳转换为隐形字符模式
    invisible_timestamp = ""
    for digit in timestamp:
        # 每个数字对应不同的隐形字符组合
        char_count = int(digit) % 3 + 1  # 1-3个字符
        base_char = ENHANCED_INVISIBLE_CHARS[int(digit) % len(ENHANCED_INVISIBLE_CHARS)]
        invisible_timestamp += base_char * char_count + '\u200C'  # 用200C作为分隔

    return invisible_timestamp


def apply_multi_layer_protection(text: str, content: str) -> str:
    """
    应用多层防护策略 - 修正版（保持URL可点击性）
    """
    # 第1层：字符间随机插入隐形字符（不影响URL识别）
    protected = add_enhanced_invisible_chars(text)

    # 第2层：添加前后隐形字符序列
    prefix = generate_random_invisible_sequence(2, 5)
    suffix = generate_random_invisible_sequence(2, 5)
    protected = prefix + protected + suffix

    # 第3层：内容指纹
    fingerprint = embed_content_fingerprint(content)

    # 第4层：时间戳
    timestamp = add_timestamp_watermark()

    # 组合所有层（指纹和时间戳作为隐形前缀）
    final_protected = fingerprint + timestamp + protected

    return final_protected


def add_invisible_chars_to_text(text: str, insertion_rate: float = 0.3) -> str:
    """
    原版隐形字符插入函数（保持向后兼容）

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
    ⚠️ 已弃用：此函数会在文章中间插入水印，影响阅读体验
    建议使用 apply_watermark_to_chapter() 替代

    Args:
        content: 原始内容
        watermark_text: 水印文本，默认为官方水印文本
        num_insertions: 插入次数，如果为None则根据内容长度自动计算

    Returns:
        原始内容（不再插入水印）
    """
    # 为了向后兼容，保留函数但不执行插入操作
    print("警告：insert_watermark 函数已弃用，请使用 apply_watermark_to_chapter()")
    return content  # 直接返回原内容，不插入水印


def apply_watermark_to_chapter(content: str) -> str:
    """
    增强版章节末尾水印 - 仅在章节末尾添加，多层防护，保持URL完全可点击

    Args:
        content: 章节内容

    Returns:
        处理后的内容
    """
    if not content:
        return content

    # 固定水印文本（强调开源免费，防止倒卖欺骗）
    base_watermark = "本小说使用开源免费工具下载：https://github.com/POf-L/Fanqie-novel-Downloader 如付费购买请立即退款举报！"

    # 应用多层防护（仅使用隐形字符，不改变可见字符）
    protected_watermark = apply_multi_layer_protection(base_watermark, content)

    # 在章节末尾添加水印（随机2-4个换行）
    random_newlines = '\n' * random.randint(2, 4)
    final_content = content + random_newlines + protected_watermark

    return final_content
