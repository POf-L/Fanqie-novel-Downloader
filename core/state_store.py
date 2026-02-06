# -*- coding: utf-8 -*-
"""下载状态持久化工具。"""

import json
import os
import tempfile
from typing import Dict, Iterable, Set


def get_status_dir() -> str:
    """获取下载状态目录（临时目录）。"""
    status_dir = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader')
    os.makedirs(status_dir, exist_ok=True)
    return status_dir


def get_status_file_path(book_id: str) -> str:
    """获取下载状态文件路径。"""
    return os.path.join(get_status_dir(), f".download_status_{book_id}.json")


def get_content_file_path(book_id: str) -> str:
    """获取已下载章节内容文件路径。"""
    return os.path.join(get_status_dir(), f".download_content_{book_id}.json")


def load_status(book_id: str) -> Set[str]:
    """加载下载状态集合。"""
    status_file = get_status_file_path(book_id)
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, list):
                    return set(str(item) for item in data)
        except Exception:
            pass
    return set()


def load_saved_content(book_id: str) -> Dict[int, Dict]:
    """加载已保存章节内容。"""
    content_file = get_content_file_path(book_id)
    if os.path.exists(content_file):
        try:
            with open(content_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return {int(key): value for key, value in data.items()}
        except Exception:
            pass
    return {}


def save_status(book_id: str, downloaded_ids: Iterable[str]):
    """保存下载状态集合。"""
    with open(get_status_file_path(book_id), 'w', encoding='utf-8') as file:
        json.dump(list(downloaded_ids), file, ensure_ascii=False, indent=2)


def save_content(book_id: str, chapter_results: Dict[int, Dict]):
    """保存章节内容。"""
    with open(get_content_file_path(book_id), 'w', encoding='utf-8') as file:
        json.dump(chapter_results, file, ensure_ascii=False, indent=2)


def clear_status(book_id: str):
    """清理状态与内容文件。"""
    status_file = get_status_file_path(book_id)
    content_file = get_content_file_path(book_id)
    if os.path.exists(status_file):
        os.remove(status_file)
    if os.path.exists(content_file):
        os.remove(content_file)


def has_saved_state(book_id: str) -> bool:
    """检查是否存在已保存状态。"""
    return os.path.exists(get_status_file_path(book_id)) or os.path.exists(get_content_file_path(book_id))

