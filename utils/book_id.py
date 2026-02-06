# -*- coding: utf-8 -*-
"""书籍ID解析工具。"""

import re
from typing import Optional


BOOK_URL_PATTERN = re.compile(r'fanqienovel\.com/page/(\d+)')


def extract_book_id(raw_value: str) -> Optional[str]:
    """从输入值中提取书籍ID，支持纯ID或URL。"""
    value = (raw_value or '').strip()
    if not value:
        return None

    match = BOOK_URL_PATTERN.search(value)
    if match:
        return match.group(1)

    if value.isdigit():
        return value
    return None


def extract_book_id_with_min_length(raw_value: str, min_length: int = 1) -> Optional[str]:
    """提取并校验最小长度（用于兼容旧逻辑场景）。"""
    book_id = extract_book_id(raw_value)
    if not book_id:
        return None
    return book_id if len(book_id) >= min_length else None
