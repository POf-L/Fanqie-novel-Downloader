# -*- coding: utf-8 -*-
"""
下载状态持久化 - 从 download_manager.py 拆分
"""

from __future__ import annotations

import json
import os
import sys

from config.config import print_lock


def _get_cache_dir() -> str:
    """获取缓存目录（保存在程序运行目录的 cache 文件夹）"""
    # 获取程序运行目录
    if getattr(sys, 'frozen', False):
        # 打包环境
        if hasattr(sys, '_MEIPASS'):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    cache_dir = os.path.join(base_dir, 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _get_status_file_path(book_id: str) -> str:
    """获取下载状态文件路径"""
    filename = f".download_status_{book_id}.json"
    return os.path.join(_get_cache_dir(), filename)


def _get_content_file_path(book_id: str) -> str:
    """获取已下载内容文件路径"""
    filename = f".download_content_{book_id}.json"
    return os.path.join(_get_cache_dir(), filename)


def load_status(book_id: str):
    """加载下载状态（从临时目录读取）"""
    status_file = _get_status_file_path(book_id)
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception:
            pass
    return set()


def load_saved_content(book_id: str) -> dict:
    """加载已保存的章节内容

    Args:
        book_id: 书籍ID

    Returns:
        dict: 已保存的章节内容 {index: {'title': ..., 'content': ...}}
    """
    content_file = _get_content_file_path(book_id)
    if os.path.exists(content_file):
        try:
            with open(content_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # 将字符串键转换为整数键
                    return {int(k): v for k, v in data.items()}
        except Exception:
            pass
    return {}


def save_status(book_id: str, downloaded_ids):
    """保存下载状态（保存到临时目录）"""
    status_file = _get_status_file_path(book_id)
    try:
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(list(downloaded_ids), f, ensure_ascii=False, indent=2)
    except Exception as e:
        with print_lock:
            print(f"保存下载状态失败: {str(e)}")


def save_content(book_id: str, chapter_results: dict):
    """保存已下载的章节内容

    Args:
        book_id: 书籍ID
        chapter_results: 章节内容 {index: {'title': ..., 'content': ...}}
    """
    content_file = _get_content_file_path(book_id)
    try:
        with open(content_file, 'w', encoding='utf-8') as f:
            json.dump(chapter_results, f, ensure_ascii=False, indent=2)
    except Exception as e:
        with print_lock:
            print(f"保存章节内容失败: {str(e)}")


def clear_status(book_id: str):
    """清除下载状态（下载完成后调用）"""
    status_file = _get_status_file_path(book_id)
    content_file = _get_content_file_path(book_id)
    try:
        if os.path.exists(status_file):
            os.remove(status_file)
        if os.path.exists(content_file):
            os.remove(content_file)
    except Exception:
        pass


def has_saved_state(book_id: str) -> bool:
    """检查是否有已保存的下载状态"""
    status_file = _get_status_file_path(book_id)
    content_file = _get_content_file_path(book_id)
    return os.path.exists(status_file) or os.path.exists(content_file)

