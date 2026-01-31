# -*- coding: utf-8 -*-
"""
异步批量下载支持 - 从 download_manager.py 拆分
"""

from __future__ import annotations

import asyncio
from typing import Dict, List

from config.config import CONFIG


class APIManagerExt:
    """扩展的API管理器，添加异步批量下载功能"""

    async def download_chapters_async(self, chapters: List[Dict], progress_callback=None) -> Dict[int, Dict]:
        """异步批量下载章节 - 替代 ThreadPoolExecutor 的高性能实现"""
        results = {}
        semaphore = asyncio.Semaphore(CONFIG.get("max_workers", 30))

        async def download_single(chapter):
            async with semaphore:
                from .api_manager import get_api_manager
                api = get_api_manager()
                content = await api.get_chapter_content_async(chapter["id"])
                if content and content.get('content'):
                    return chapter['index'], {
                        'title': chapter['title'],
                        'content': content.get('content', '')
                    }
                return None

        tasks = [download_single(ch) for ch in chapters]

        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                idx, data = result
                results[idx] = data
                completed += 1
                if progress_callback:
                    progress = int((completed / len(chapters)) * 100)
                    progress_callback(progress, f"已下载 {completed}/{len(chapters)} 章")

        return results

    def download_chapters(self, chapters: List[Dict], progress_callback=None) -> Dict[int, Dict]:
        """下载章节列表（保持向后兼容）"""
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(self.download_chapters_async(chapters, progress_callback))
        except RuntimeError:
            return asyncio.run(self.download_chapters_async(chapters, progress_callback))

