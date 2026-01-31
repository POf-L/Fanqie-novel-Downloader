# -*- coding: utf-8 -*-
"""
APIManager 书籍信息相关方法 - 从 api_manager.py 拆分
"""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

import aiohttp
import requests

from config.config import CONFIG, print_lock, get_headers


class APIManagerBooksMixin:
    """书籍信息/目录/章节列表"""

    async def get_directory_async(self, book_id: str) -> Optional[List[Dict]]:
        """异步获取简化目录（更快，标题与整本下载内容一致）"""
        try:
            session = await self._get_async_session()
            state = self._get_async_state()
            semaphore = state.get('semaphore')
            rate_limiter = state.get('rate_limiter')
            url = f"{self.base_url}/api/directory"
            params = {"fq_id": book_id}

            async with semaphore:
                if rate_limiter:
                    await rate_limiter.acquire()

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200 and "data" in data:
                            lists = data["data"].get("lists", [])
                            if lists:
                                return lists
            return None
        except Exception:
            return None
    async def get_chapter_list_async(self, book_id: str) -> Optional[List[Dict]]:
        """异步获取章节列表"""
        try:
            session = await self._get_async_session()
            state = self._get_async_state()
            semaphore = state.get('semaphore')
            rate_limiter = state.get('rate_limiter')
            url = f"{self.base_url}{self.endpoints['book']}"
            params = {"book_id": book_id}

            async with semaphore:
                if rate_limiter:
                    await rate_limiter.acquire()

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200 and "data" in data:
                            level1_data = data["data"]
                            if isinstance(level1_data, dict) and "data" in level1_data:
                                return level1_data["data"]
                            return level1_data
            return None
        except Exception as e:
            from utils.async_logger import safe_print
            safe_print(f"异步获取章节列表失败: {str(e)}")
            return None
    def search_books(self, keyword: str, offset: int = 0) -> Optional[Dict]:
        """搜索书籍"""
        try:
            self.ensure_base_url()
            url = f"{self.base_url}{self.endpoints['search']}"
            params = {"key": keyword, "tab_type": "3", "offset": str(offset)}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return data
            return None
        except Exception as e:
            from utils.async_logger import safe_print
            safe_print(f"搜索异常: {str(e)}")
            return None
    def get_book_detail(self, book_id: str) -> Optional[Dict]:
        """获取书籍详情，返回 dict 或 None，如果书籍下架会返回 {'_error': 'BOOK_REMOVE'}"""
        try:
            self.ensure_base_url()
            url = f"{self.base_url}{self.endpoints['detail']}"
            params = {"book_id": book_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    level1_data = data["data"]
                    # 检查是否有错误信息（如书籍下架）
                    if isinstance(level1_data, dict):
                        inner_msg = level1_data.get("message", "")
                        inner_code = level1_data.get("code")
                        if inner_msg == "BOOK_REMOVE" or inner_code == 101109:
                            return {"_error": "BOOK_REMOVE", "_message": "书籍已下架"}
                        if "data" in level1_data:
                            inner_data = level1_data["data"]
                            # 如果内层 data 是空的，也可能是下架
                            if isinstance(inner_data, dict) and not inner_data and inner_msg:
                                return {"_error": inner_msg, "_message": inner_msg}
                            return inner_data
                    return level1_data
            return None
        except Exception as e:
            from utils.async_logger import safe_print
            safe_print(f"获取书籍详情异常: {str(e)}")
            return None
    def get_directory(self, book_id: str) -> Optional[List[Dict]]:
        self.ensure_base_url()
        """获取简化目录（更快，标题与整本下载内容一致）
        GET /api/directory - 参数: fq_id
        """
        try:
            url = f"{self.base_url}/api/directory"
            params = {"fq_id": book_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    lists = data["data"].get("lists", [])
                    if lists:
                        return lists
            return None
        except Exception:
            return None
    def get_chapter_list(self, book_id: str) -> Optional[List[Dict]]:
        self.ensure_base_url()
        """获取章节列表"""
        try:
            from utils.async_logger import safe_print
            safe_print(f"[DEBUG] 开始获取章节列表: ID={book_id}")
                
            url = f"{self.base_url}{self.endpoints['book']}"
            params = {"book_id": book_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            safe_print(f"[DEBUG] 章节列表响应: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    level1_data = data["data"]
                    if isinstance(level1_data, dict) and "data" in level1_data:
                        return level1_data["data"]
                    return level1_data
            return None
        except Exception as e:
            from utils.async_logger import safe_print
            safe_print(f"获取章节列表异常: {str(e)}")
            return None
