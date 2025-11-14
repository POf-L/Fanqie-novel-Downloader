# -*- coding: utf-8 -*-
"""
番茄小说下载器核心模块 - 基于test.py的完整实现
"""

import time
import requests
import bs4
import re
import os
import random
import json
import urllib3
import threading
import signal
import sys
import inspect
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
from tqdm import tqdm
from collections import OrderedDict
from fake_useragent import UserAgent
from typing import Optional, Dict
from ebooklib import epub
import base64
import gzip
from urllib.parse import urlencode
from config import CONFIG, print_lock, get_headers  # 使用config中的配置
import aiohttp
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, List, Optional

# 禁用SSL证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

# ===================== API管理器类（从api_manager.py合并）=====================

class APIManager:
    """新API管理器 - 直接使用 api-return.cflin.ddns-ip.net"""
    
    def __init__(self):
        self.base_url = CONFIG["api_base_url"]
        self.api_endpoint = CONFIG["api_endpoint"]
        self.full_url = f"{self.base_url}{self.api_endpoint}"
        # 线程本地会话，复用连接，减少握手
        self._tls = threading.local()

    def _get_session(self) -> requests.Session:
        sess = getattr(self._tls, 'session', None)
        if sess is None:
            sess = requests.Session()
            retries = Retry(
                total=CONFIG.get("max_retries", 5),  # 使用配置的重试次数
                backoff_factor=0.3,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET", "POST"),
                raise_on_status=False,
            )
            # 适度的连接池大小（遵守API限制）
            pool_size = CONFIG.get("connection_pool_size", 4)
            adapter = HTTPAdapter(
                pool_connections=pool_size, 
                pool_maxsize=pool_size, 
                max_retries=retries,
                pool_block=False  # 不阻塞等待连接
            )
            sess.mount('http://', adapter)
            sess.mount('https://', adapter)
            # 保持连接活跃
            sess.headers.update({'Connection': 'keep-alive'})
            self._tls.session = sess
        return sess
    
    def search_books(self, keyword: str) -> Optional[Dict]:
        """搜索书籍
        参数:
            keyword: 搜索关键词
        返回:
            搜索结果字典或None
        """
        try:
            # 使用新的搜索接口
            search_url = f"{self.base_url}{CONFIG['tomato_endpoints']['search']}"
            params = {"key": keyword, "tab_type": "3", "offset": "0"}
            response = self._get_session().get(search_url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                
                # 根据新API文档处理响应
                if data.get("code") == 200 and "data" in data:
                    # 解析嵌套的响应结构
                    inner_data = data.get("data", {})
                    if isinstance(inner_data, dict) and "search_tabs" in inner_data:
                        # 查找书籍标签页 (tab_type = 3)
                        search_tabs = inner_data.get("search_tabs", [])
                        for tab in search_tabs:
                            if tab.get("tab_type") == 3 and tab.get("data"):
                                # 提取书籍数据
                                books_data = []
                                for item in tab.get("data", []):
                                    if "book_data" in item and isinstance(item["book_data"], list):
                                        books_data.extend(item["book_data"])
                                
                                return {
                                    "code": 200,
                                    "data": books_data,
                                    "message": "success"
                                }
                    # 标准响应格式
                    return data
                elif "data" in data:
                    # 兼容其他可能的格式
                    if isinstance(data["data"], list):
                        return {
                            "code": 200,
                            "data": data["data"],
                            "message": "success"
                        }
                    elif isinstance(data["data"], dict) and "books" in data["data"]:
                        return {
                            "code": 200,
                            "data": data["data"]["books"],
                            "message": "success"
                        }
                else:
                    with print_lock:
                        print(f"搜索失败: {data.get('message', '未知响应格式')}")
            else:
                with print_lock:
                    print(f"搜索请求失败，状态码: {response.status_code}")
            return None
        except Exception as e:
            with print_lock:
                print(f"搜索异常: {str(e)}")
            return None
    
    def get_book_info(self, book_id: str) -> Optional[Dict]:
        """获取书籍信息
        参数:
            book_id: 书籍ID
        返回:
            书籍信息字典或None
        """
        try:
            # 使用新的详情接口
            detail_url = f"{self.base_url}{CONFIG['tomato_endpoints']['detail']}"
            params = {"book_id": book_id}
            response = self._get_session().get(detail_url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()

                # 根据新API文档处理响应
                if data.get("code") == 200 and "data" in data:
                    inner = data.get("data")

                    # 兼容数据嵌套 {code:0,data:{...}}
                    if isinstance(inner, dict) and "data" in inner and len(inner) <= 3:
                        inner = inner.get("data")

                    if isinstance(inner, dict):
                        return inner
                    with print_lock:
                        print(f"书籍信息响应格式不符: {type(inner)}")
                    return None

                with print_lock:
                    print(f"获取书籍信息失败: {data.get('message', '未知响应格式')}")
            else:
                with print_lock:
                    print(f"获取书籍信息请求失败，状态码: {response.status_code}")
            return None
        except Exception as e:
            with print_lock:
                print(f"获取书籍信息异常: {str(e)}")
            return None
    
    def get_chapter_list(self, book_id: str) -> Optional[List[Dict]]:
        """获取章节列表
        参数:
            book_id: 书籍ID
        返回:
            章节列表或None
        """
        try:
            # 使用新的目录接口
            book_url = f"{self.base_url}{CONFIG['tomato_endpoints']['book']}"
            params = {"book_id": book_id}
            response = self._get_session().get(book_url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                
                # 根据新API文档处理响应 
                if data.get("code") == 200 and "data" in data:
                    # 兼容双层data：{code:200, data:{code:0, data:{...}}}
                    inner = data.get("data")
                    if isinstance(inner, dict) and "data" in inner and ("allItemIds" not in inner and "chapterListWithVolume" not in inner and "chapters" not in inner):
                        inner = inner.get("data")
                    
                    # 如果data是列表，直接返回
                    if isinstance(inner, list):
                        # 统一格式
                        formatted_chapters = []
                        for ch in inner:
                            formatted_chapters.append({
                                "chapter_id": ch.get("item_id", ch.get("chapter_id", "")),
                                "chapter_name": ch.get("title", ch.get("chapter_name", "")),
                                "volume_name": ch.get("volume_name", "")
                            })
                        return formatted_chapters
                    # 如果data是字典且包含chapters
                    elif isinstance(inner, dict) and "chapters" in inner:
                        chapters = inner["chapters"]
                        # 统一格式
                        formatted_chapters = []
                        for ch in chapters:
                            formatted_chapters.append({
                                "chapter_id": ch.get("item_id", ch.get("chapter_id", "")),
                                "chapter_name": ch.get("title", ch.get("chapter_name", "")),
                                "volume_name": ch.get("volume_name", "")
                            })
                        
                        return formatted_chapters
                    # 如果data是字典且包含新目录结构（allItemIds/chapterListWithVolume）
                    elif isinstance(inner, dict) and ("allItemIds" in inner or "chapterListWithVolume" in inner):
                        raw = inner
                        formatted_chapters = []
                        chapter_list_with_volume = raw.get("chapterListWithVolume", [])
                        if chapter_list_with_volume:
                            idx = 0
                            for volume_chapters in chapter_list_with_volume:
                                if isinstance(volume_chapters, list):
                                    for ch in volume_chapters:
                                        if isinstance(ch, dict):
                                            item_id = ch.get("itemId") or ch.get("item_id") or ch.get("id")
                                            title = ch.get("title") or ch.get("chapter_name") or f"第{idx+1}章"
                                            if item_id:
                                                formatted_chapters.append({
                                                    "chapter_id": str(item_id),
                                                    "chapter_name": title,
                                                    "volume_name": ch.get("volume_name", "")
                                                })
                                                idx += 1
                                elif isinstance(volume_chapters, dict):
                                    chapters = volume_chapters.get("chapterList", [])
                                    for ch in chapters:
                                        item_id = ch.get("itemId") or ch.get("item_id") or ch.get("id")
                                        title = ch.get("title") or ch.get("chapter_name") or f"第{idx+1}章"
                                        if item_id:
                                            formatted_chapters.append({
                                                "chapter_id": str(item_id),
                                                "chapter_name": title,
                                                "volume_name": ch.get("volume_name", "")
                                            })
                                            idx += 1
                        else:
                            # 只有ID列表时（allItemIds），生成默认标题
                            for idx, item_id in enumerate(raw.get("allItemIds", [])):
                                if item_id:
                                    formatted_chapters.append({
                                        "chapter_id": str(item_id),
                                        "chapter_name": f"第{idx+1}章",
                                        "volume_name": ""
                                    })
                        return formatted_chapters if formatted_chapters else None
                    else:
                        with print_lock:
                            print(f"章节列表响应格式不符: {type(data['data'])}")
                        return None
                        
                # 兼容其他格式
                elif "data" in data and isinstance(data["data"], list):
                    # 统一格式
                    formatted_chapters = []
                    for ch in data["data"]:
                        formatted_chapters.append({
                            "chapter_id": ch.get("item_id", ch.get("chapter_id", "")),
                            "chapter_name": ch.get("title", ch.get("chapter_name", "")),
                            "volume_name": ch.get("volume_name", "")
                        })
                    return formatted_chapters
                else:
                    with print_lock:
                        print(f"获取章节列表失败: {data.get('message', '未知响应格式')}")
            else:
                with print_lock:
                    print(f"获取章节列表请求失败，状态码: {response.status_code}")
            return None
        except Exception as e:
            with print_lock:
                print(f"获取章节列表异常: {str(e)}")
            return None
    
    def get_chapter_content(self, chapter_id: str) -> Optional[Dict]:
        """获取章节内容
        参数:
            chapter_id: 章节ID (格式: 书籍ID_章节序号)
        返回:
            章节内容字典或None
        """
        try:
            # 使用新的内容接口
            content_url = f"{self.base_url}{CONFIG['tomato_endpoints']['content']}"
            params = {"tab": "小说", "item_id": chapter_id}
            response = self._get_session().get(content_url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                
                # 根据新API文档处理响应
                if data.get("code") == 200 and "data" in data:
                    # 标准响应格式
                    if isinstance(data["data"], dict):
                        return data["data"]
                    # 如果data直接是字符串（纯文本内容）
                    elif isinstance(data["data"], str):
                        return {"content": data["data"], "title": "", "item_id": chapter_id}
                    else:
                        with print_lock:
                            print(f"章节内容响应格式不符: {type(data['data'])}")
                        return None
                else:
                    with print_lock:
                        print(f"获取章节内容失败: {data.get('message', '未知响应格式')}")
            else:
                with print_lock:
                    print(f"获取章节内容请求失败，状态码: {response.status_code}")
            return None
        except Exception as e:
            with print_lock:
                print(f"获取章节内容异常: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """测试API连接
        返回:
            True如果连接成功，False否则
        """
        try:
            # 测试搜索接口是否可用
            search_url = f"{self.base_url}{CONFIG['tomato_endpoints']['search']}"
            params = {"key": "测试", "tab_type": "3", "offset": "0"}
            response = self._get_session().get(search_url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    # 静默成功，减少输出
                    return True
                    
            return False
        except Exception:
            # 静默失败，避免刷屏
            return False

# 全局API管理器实例（延迟初始化）
api_manager = None

def get_api_manager():
    """获取API管理器实例，延迟初始化"""
    global api_manager
    if api_manager is None:
        try:
            api_manager = APIManager()
        except Exception as e:
            with print_lock:
                print(f"[API] API管理器初始化失败: {str(e)}")
            return None
    return api_manager

class TomatoAPI:
    """对接 cenguigui 番茄 API 的同步客户端"""

    def __init__(self):
        self.base_url = CONFIG.get("tomato_api_base", "")
        self.endpoints = CONFIG.get("tomato_endpoints", {})
        self._tls = threading.local()

    def _get_session(self) -> requests.Session:
        sess = getattr(self._tls, 'session', None)
        if sess is None:
            sess = requests.Session()
            retries = Retry(
                total=CONFIG.get("max_retries", 3),
                backoff_factor=0.3,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(
                pool_connections=CONFIG.get("connection_pool_size", 4),
                pool_maxsize=CONFIG.get("connection_pool_size", 4),
                max_retries=retries,
                pool_block=False
            )
            sess.mount('http://', adapter)
            sess.mount('https://', adapter)
            sess.headers.update({'Connection': 'keep-alive'})
            self._tls.session = sess
        return sess

    def _url(self, key: str) -> str:
        return f"{self.base_url}{self.endpoints.get(key, '')}"

    def test_connection(self) -> bool:
        try:
            url = self._url('search')
            params = {"key": "测试", "tab_type": "3", "offset": "0"}
            r = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            return r.status_code == 200
        except Exception:
            return False

    def search(self, keyword: str, offset: int = 0) -> Optional[Dict]:
        """搜索书籍
        Args:
            keyword: 搜索关键词
            offset: 偏移量
        Returns:
            搜索结果字典
        """
        try:
            url = self._url('search')
            params = {"key": keyword, "tab_type": "3", "offset": str(offset or 0)}
            resp = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            if resp.status_code != 200:
                return None
            data = resp.json()

            books_list = []
            
            # 处理新的search_tabs格式
            if 'search_tabs' in data and isinstance(data['search_tabs'], list):
                for tab in data['search_tabs']:
                    if not isinstance(tab, dict):
                        continue
                    
                    # 检查tab中的data字段
                    tab_data = tab.get('data', [])
                    if not isinstance(tab_data, list):
                        continue
                    
                    # 遍历每个数据项
                    for item in tab_data:
                        if not isinstance(item, dict):
                            continue
                        
                        # 获取book_data
                        book_data = item.get('book_data', [])
                        if not isinstance(book_data, list):
                            continue
                        
                        # 处理每本书
                        for book in book_data:
                            book_id = book.get('book_id') or book.get('id')
                            if book_id:
                                books_list.append({
                                    'book_id': str(book_id),
                                    'book_name': book.get('book_name') or book.get('title') or '',
                                    'author': book.get('author') or book.get('author_name') or '未知作者',
                                    'intro': book.get('abstract') or book.get('intro') or '',
                                    'cover': book.get('thumb_url') or book.get('cover_url') or '',
                                    'category': book.get('category') or '',
                                    'word_count': book.get('word_number') or '',
                                    'chapter_count': book.get('serial_count') or '',
                                    'status': book.get('creation_status') or ''
                                })
            
            # 如果没有search_tabs，尝试直接从 data 字段获取
            elif 'data' in data:
                raw = data['data']
                candidates = []
                if isinstance(raw, list):
                    candidates = raw
                elif isinstance(raw, dict):
                    for key in ['books', 'items', 'results', 'list']:
                        if isinstance(raw.get(key), list):
                            candidates = raw.get(key)
                            break
                
                for it in candidates:
                    book_id = it.get('book_id') or it.get('id')
                    if book_id:
                        books_list.append({
                            'book_id': str(book_id),
                            'book_name': it.get('book_name') or it.get('title') or '',
                            'author': it.get('author') or it.get('author_name') or '未知作者',
                            'intro': it.get('abstract') or it.get('intro') or '',
                            'cover': it.get('thumb_url') or it.get('cover_url') or '',
                            'category': it.get('category') or '',
                            'word_count': it.get('word_number') or '',
                            'chapter_count': it.get('serial_count') or '',
                            'status': it.get('creation_status') or ''
                        })

            return {"books": books_list, "raw": data}
        except Exception as e:
            with print_lock:
                print(f"搜索异常: {str(e)}")
            return None

    def get_book_detail(self, book_id: str) -> Optional[Dict]:
        try:
            url = self._url('detail')
            params = {"book_id": book_id}
            resp = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            if resp.status_code != 200:
                return None
            data = resp.json()
            raw = data.get('data', data)
            if isinstance(raw, dict) and 'data' in raw and len(raw) <= 3:
                raw = raw.get('data')
            if isinstance(raw, dict):
                return {
                    'book_id': str(raw.get('book_id') or book_id),
                    'book_name': raw.get('book_name') or raw.get('title') or '',
                    'original_book_name': raw.get('original_book_name') or '',
                    'author': raw.get('author') or raw.get('author_name') or '未知作者',
                    'intro': raw.get('intro') or raw.get('abstract') or raw.get('desc') or '',
                    'cover': raw.get('cover') or raw.get('cover_url') or raw.get('thumb_url') or ''
                }
            return None
        except Exception:
            return None

    def get_all_items(self, book_id: str) -> Optional[list]:
        """优先调用 book 接口获取目录，必要时回退到直接访问 book_id"""
        headers = get_headers()
        try:
            # 先尝试 book 接口
            url = self._url('book')
            params = {"book_id": book_id}
            resp = self._get_session().get(url, params=params, headers=headers, timeout=CONFIG["request_timeout"])
            if resp.status_code == 200:
                data = resp.json()
                
                if data.get('code') == 200 and 'data' in data:
                    raw = data['data']
                    # 兼容双层data：{code:200, data:{code:0, data:{...}}}
                    if isinstance(raw, dict) and 'data' in raw and ("allItemIds" not in raw and "chapterListWithVolume" not in raw and not isinstance(raw.get('data'), list)):
                        raw = raw.get('data')
                    items = []
                    
                    # 处理新格式：{"allItemIds": [...], "volumeNameList": [...], "chapterListWithVolume": [...]}
                    if isinstance(raw, dict) and 'allItemIds' in raw:
                        all_item_ids = raw.get('allItemIds', [])
                        # 检查是否有 chapterListWithVolume 提供详细信息
                        chapter_list_with_volume = raw.get('chapterListWithVolume', [])
                        
                        # 如果有章节详细信息
                        if chapter_list_with_volume:
                            idx = 0
                            # chapterListWithVolume 是一个嵌套数组 [[chapters_of_vol1], [chapters_of_vol2], ...]
                            for volume_chapters in chapter_list_with_volume:
                                if isinstance(volume_chapters, list):
                                    # 遍历该卷的章节
                                    for ch in volume_chapters:
                                        if isinstance(ch, dict):
                                            # 注意字段名是 itemId 不是 item_id
                                            item_id = ch.get('itemId') or ch.get('item_id') or ch.get('id')
                                            title = ch.get('title') or ch.get('chapter_name') or f"第{idx+1}章"
                                            if item_id:
                                                items.append({
                                                    'item_id': str(item_id),
                                                    'title': title,
                                                    'index': idx
                                                })
                                                idx += 1
                                # 如果volume_chapters是字典格式（兼容其他可能的格式）
                                elif isinstance(volume_chapters, dict):
                                    chapters = volume_chapters.get('chapterList', [])
                                    for ch in chapters:
                                        item_id = ch.get('itemId') or ch.get('item_id') or ch.get('id')
                                        title = ch.get('title') or ch.get('chapter_name') or f"第{idx+1}章"
                                        if item_id:
                                            items.append({
                                                'item_id': str(item_id),
                                                'title': title,
                                                'index': idx
                                            })
                                            idx += 1
                        else:
                            # 只有ID列表，生成默认标题
                            for idx, item_id in enumerate(all_item_ids):
                                if item_id:
                                    items.append({
                                        'item_id': str(item_id),
                                        'title': f"第{idx+1}章",
                                        'index': idx
                                    })
                        
                        if items:
                            return items
                    
                    # 处理旧格式（直接是章节列表）
                    elif isinstance(raw, list):
                        for idx, ch in enumerate(raw):
                            item_id = ch.get('item_id') or ch.get('chapter_id') or ch.get('id')
                            title = ch.get('title') or ch.get('chapter_name') or f"第{idx+1}章"
                            if item_id:
                                items.append({
                                    'item_id': str(item_id),
                                    'title': title,
                                    'index': idx
                                })
                        if items:
                            return items
                    
        except Exception as e:
            with print_lock:
                print(f"all_items接口异常: {str(e)}")
        
        # 回退到directory接口
        try:
            url = self._url('directory')
            params = {"book_id": book_id, "fq_id": book_id}  # 同时传递book_id与fq_id以提高兼容性
            resp = self._get_session().get(url, params=params, headers=headers, timeout=CONFIG["request_timeout"])
            
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            if data.get('code') not in [0, 200] or not data.get('data'):
                return None
            
            raw = data['data']
            items = []
            
            # 处理简化目录格式
            if isinstance(raw, list):
                for idx, ch in enumerate(raw):
                    item_id = ch.get('item_id') or ch.get('id')
                    title = ch.get('title') or ch.get('chapter_name') or f"第{idx+1}章"
                    if item_id:
                        items.append({
                            'item_id': str(item_id),
                            'title': title,
                            'index': idx
                        })
            
            return items if items else None
            
        except Exception as e:
            with print_lock:
                print(f"catalog接口异常: {str(e)}")
            return None

    def get_content(self, item_id: str) -> Optional[Dict]:
        try:
            url = self._url('content')
            params = {"tab": "小说", "item_id": item_id}
            resp = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            if resp.status_code != 200:
                return None
            data = resp.json()
            raw = data.get('data', data)
            if isinstance(raw, dict):
                content = raw.get('content') or raw.get('text') or ''
                title = raw.get('chapter_name') or raw.get('title') or ''
                return {'item_id': str(item_id), 'title': title, 'content': content}
            return None
        except Exception:
            return None

    def get_multi_content(self, book_id: str, item_ids: list) -> Optional[list]:
        """批量获取章节内容
        Args:
            book_id: 书籍ID
            item_ids: 章节ID列表
        Returns:
            章节内容列表或None
        """
        try:
            url = self._url('multi_content')
            params = {
                "tab": "批量",
                "item_ids": ','.join(map(str, item_ids)),
                "book_id": book_id
            }
            resp = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            if resp.status_code != 200:
                with print_lock:
                    print(f"批量获取章节内容失败，状态码: {resp.status_code}")
                return None

            data = resp.json()
            if data.get('code') != 200:
                with print_lock:
                    print(f"批量获取失败: {data.get('message', '未知错误')}")
                return None

            raw = data.get('data', data)
            results = []

            def collect_entries(payload):
                entries = []
                if isinstance(payload, dict):
                    chapters = payload.get('chapters')
                    if isinstance(chapters, list):
                        for ch in chapters:
                            if isinstance(ch, dict):
                                entries.append(ch)
                    elif 'data' in payload:
                        entries.extend(collect_entries(payload.get('data')))
                    else:
                        for key, val in payload.items():
                            if isinstance(val, dict):
                                enriched = dict(val)
                                enriched.setdefault('item_id', key)
                                entries.append(enriched)
                elif isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            entries.append(item)
                return entries

            def normalize_entry(entry):
                if not isinstance(entry, dict):
                    return
                novel_data = entry.get('novel_data')
                item_id = entry.get('item_id') or entry.get('chapter_id')
                title = entry.get('chapter_name') or entry.get('title') or ''
                if isinstance(novel_data, dict):
                    item_id = item_id or novel_data.get('item_id')
                    title = title or novel_data.get('title') or novel_data.get('chapter_title') or ''
                content = entry.get('content') or entry.get('text') or ''
                if item_id and content:
                    results.append({
                        'item_id': str(item_id),
                        'title': title,
                        'content': content
                    })

            for entry in collect_entries(raw):
                normalize_entry(entry)

            if results:
                result_map = {r['item_id']: r for r in results}
                ordered_results = []
                for iid in item_ids:
                    key = str(iid)
                    if key in result_map:
                        ordered_results.append(result_map[key])
                return ordered_results if ordered_results else results

            return None

        except Exception as e:
            with print_lock:
                print(f"批量获取章节内容异常: {str(e)}")
            return None


# 全局 Tomato API 实例（延迟初始化）
tomato_api = None

def get_tomato_api():
    """获取Tomato API实例，延迟初始化"""
    global tomato_api
    if tomato_api is None:
        try:
            tomato_api = TomatoAPI()
        except Exception as e:
            with print_lock:
                print(f"[API] Tomato API初始化失败: {str(e)}")
            return None
    return tomato_api

class AsyncAPIManager:
    """异步API管理器，使用 aiohttp - 带速率限制版"""
    def __init__(self):
        self.base_url = CONFIG["api_base_url"]
        self.api_endpoint = CONFIG["api_endpoint"]
        self.full_url = f"{self.base_url}{self.api_endpoint}"
        self._session: Optional[aiohttp.ClientSession] = None
        self.semaphore = None  # 用于控制并发数
        self.rate_limiter = None  # 速率限制器
        self.last_request_time = 0  # 上次请求时间
        self.request_lock = asyncio.Lock()  # 请求锁，确保速率限制的准确性

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=CONFIG["request_timeout"],
                connect=5,  # 连接超时
                sock_read=15  # 读取超时
            )
            # 适度的连接池大小（遵守API速率限制）
            connector = aiohttp.TCPConnector(
                limit=CONFIG.get("connection_pool_size", 4),  # 总连接数
                limit_per_host=CONFIG.get("connection_pool_size", 4),  # 每个主机的连接数
                ttl_dns_cache=300,  # DNS缓存时间
                enable_cleanup_closed=True,  # 自动清理关闭的连接
                force_close=False,  # 复用连接
                keepalive_timeout=30  # 保持连接时间
            )
            self._session = aiohttp.ClientSession(
                headers=get_headers(), 
                timeout=timeout, 
                connector=connector,
                trust_env=True  # 使用系统代理设置
            )
            # 初始化信号量控制并发（根据API限制设置）
            self.semaphore = asyncio.Semaphore(CONFIG.get("api_rate_limit", 2))
            # 初始化速率限制器
            self.rate_limiter = asyncio.Semaphore(CONFIG.get("api_rate_limit", 2))
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()

    async def get_chapter_content_async(self, chapter_id: str, retry_count: int = 0) -> Optional[Dict]:
        """异步获取章节内容，支持自动重试和速率限制"""
        max_retries = CONFIG.get("max_retries", 3)
        
        async with self.semaphore:  # 使用信号量控制并发
            # 实施速率限制：确保每秒不超过2个请求
            async with self.request_lock:
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                if time_since_last < 0.5:  # 确保请求间隔至少0.5秒
                    await asyncio.sleep(0.5 - time_since_last)
                
                self.last_request_time = time.time()
            
            session = await self._get_session()
            params = {"tab": "小说", "item_id": chapter_id}
            
            for attempt in range(max_retries):
                try:
                    async with session.get(self.full_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("code") == 200 and "data" in data:
                                if isinstance(data["data"], dict):
                                    return data["data"]
                                if isinstance(data["data"], str):
                                    return {"content": data["data"], "title": "", "item_id": chapter_id}
                        elif response.status == 429:  # 速率限制
                            await asyncio.sleep(min(2 ** attempt, 10))  # 指数退避
                            continue
                        return None
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    return None
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.3)
                        continue
                    return None
            
            return None
    
    async def warmup_connection_pool(self):
        """预热连接池，建立初始连接"""
        try:
            session = await self._get_session()
            # 发送一个简单的请求来建立连接
            async with session.head(self.base_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                pass
        except:
            pass  # 忽略预热失败

# 全局异步API管理器实例（延迟初始化）
async_api_manager = None

def get_async_api_manager():
    """获取异步API管理器实例，延迟初始化"""
    global async_api_manager
    if async_api_manager is None:
        try:
            async_api_manager = AsyncAPIManager()
        except Exception as e:
            with print_lock:
                print(f"[API] 异步API管理器初始化失败: {str(e)}")
            return None
    return async_api_manager

class AsyncTomatoAPI:
    """对接 cenguigui 番茄 API 的异步客户端（仅实现批量正文）"""
    def __init__(self):
        self.base_url = CONFIG.get("tomato_api_base", "")
        self.endpoints = CONFIG.get("tomato_endpoints", {})
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=CONFIG["request_timeout"], connect=5, sock_read=20)
            connector = aiohttp.TCPConnector(
                limit=CONFIG.get("connection_pool_size", 4),
                limit_per_host=CONFIG.get("connection_pool_size", 4),
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                keepalive_timeout=30
            )
            self._session = aiohttp.ClientSession(headers=get_headers(), timeout=timeout, connector=connector, trust_env=True)
        return self._session

    def _url(self, key: str) -> str:
        return f"{self.base_url}{self.endpoints.get(key, '')}"

    async def close(self):
        if self._session:
            await self._session.close()

    async def get_multi_content_async(self, book_id: str, item_ids: list) -> Optional[list]:
        """异步批量获取章节内容
        Args:
            book_id: 书籍ID
            item_ids: 章节ID列表
        Returns:
            章节内容列表或None
        """
        try:
            session = await self._get_session()
            url = self._url('multi_content')
            params = {
                "tab": "批量",
                "item_ids": ','.join(map(str, item_ids)),
                "book_id": book_id
            }

            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    with print_lock:
                        print(f"异步批量获取失败，状态码: {resp.status}")
                    return None

                data = await resp.json()
                if data.get('code') != 200:
                    with print_lock:
                        print(f"异步批量获取失败: {data.get('message', '未知错误')}" )
                    return None

                raw = data.get('data', data)
                results = []

                def collect_entries(payload):
                    entries = []
                    if isinstance(payload, dict):
                        chapters = payload.get('chapters')
                        if isinstance(chapters, list):
                            for ch in chapters:
                                if isinstance(ch, dict):
                                    entries.append(ch)
                        elif 'data' in payload:
                            entries.extend(collect_entries(payload.get('data')))
                        else:
                            for key, val in payload.items():
                                if isinstance(val, dict):
                                    enriched = dict(val)
                                    enriched.setdefault('item_id', key)
                                    entries.append(enriched)
                    elif isinstance(payload, list):
                        for item in payload:
                            if isinstance(item, dict):
                                entries.append(item)
                    return entries

                def normalize_entry(entry):
                    if not isinstance(entry, dict):
                        return
                    novel_data = entry.get('novel_data')
                    item_id = entry.get('item_id') or entry.get('chapter_id')
                    title = entry.get('chapter_name') or entry.get('title') or ''
                    if isinstance(novel_data, dict):
                        item_id = item_id or novel_data.get('item_id')
                        title = title or novel_data.get('title') or novel_data.get('chapter_title') or ''
                    content = entry.get('content') or entry.get('text') or ''
                    if item_id and content:
                        results.append({
                            'item_id': str(item_id),
                            'title': title,
                            'content': content
                        })

                for entry in collect_entries(raw):
                    normalize_entry(entry)

                if results:
                    result_map = {r['item_id']: r for r in results}
                    ordered_results = []
                    for iid in item_ids:
                        key = str(iid)
                        if key in result_map:
                            ordered_results.append(result_map[key])
                    return ordered_results if ordered_results else results

                return None

        except asyncio.TimeoutError:
            with print_lock:
                print("异步批量获取超时")
            return None
        except Exception as e:
            with print_lock:
                print(f"异步批量获取异常: {str(e)}")
            return None


# 全局异步 Tomato API 实例


async_tomato_api = AsyncTomatoAPI()

# ===================== 原有的小说下载功能 =====================


def process_chapter_content(content):
    """处理章节内容"""
    if not content or not isinstance(content, str):
        return ""

    try:
        paragraphs = []
        if '<p idx=' in content:
            paragraphs = re.findall(r'<p idx="\d+">(.*?)</p>', content, re.DOTALL)
        else:
            paragraphs = content.split('\n')

        if paragraphs:
            first_para = paragraphs[0].strip()
            if not first_para.startswith('    '):
                paragraphs[0] = '    ' + first_para

        cleaned_content = "\n".join(p.strip() for p in paragraphs if p.strip())
        formatted_content = '\n'.join('    ' + line if line.strip() else line
                                    for line in cleaned_content.split('\n'))

        formatted_content = re.sub(r'<header>.*?</header>', '', formatted_content, flags=re.DOTALL)
        formatted_content = re.sub(r'<footer>.*?</footer>', '', formatted_content, flags=re.DOTALL)
        formatted_content = re.sub(r'</?article>', '', formatted_content)
        formatted_content = re.sub(r'<[^>]+>', '', formatted_content)
        formatted_content = re.sub(r'\\u003c|\\u003e', '', formatted_content)

        # 压缩多余的空行
        formatted_content = re.sub(r'\n{3,}', '\n\n', formatted_content).strip()
        return formatted_content
    except Exception as e:
        with print_lock:
            print(f"内容处理错误: {str(e)}")
        return str(content)


def down_text(chapter_id, headers, book_id=None):
    """下载章节内容 - 使用新API"""
    try:
        # 使用新API获取章节内容
        manager = get_api_manager()
        if manager is None:
            return None
        chapter_data = manager.get_chapter_content(chapter_id)
        
        if chapter_data:
            content = chapter_data.get("content", "")
            title = chapter_data.get("chapter_name", "")
            
            if content:
                # 处理章节内容格式
                processed_content = process_chapter_content(content)
                processed = re.sub(r'^(\s*)', r'    ', processed_content, flags=re.MULTILINE)
                return title, processed
        
        with print_lock:
            print(f"章节 {chapter_id} 下载失败")
        return None, None
        
    except Exception as e:
        with print_lock:
            print(f"下载章节 {chapter_id} 异常: {str(e)}")
        return None, None


def get_chapters_from_api(book_id, headers):
    """从新番茄API获取章节列表（优先 all_items.php 回退 catalog.php）"""
    try:
        api = get_tomato_api()
        if api is None:
            return None
        items = api.get_all_items(book_id)
        if not items:
            with print_lock:
                print("无法获取章节列表")
            return None
        final_chapters = []
        for ch in items:
            final_chapters.append({
                "id": ch.get("item_id", ""),
                "title": ch.get("title", ""),
                "index": ch.get("index", 0)
            })
        return final_chapters
    except Exception as e:
        with print_lock:
            print(f"获取章节列表失败: {str(e)}")
        return None


def get_book_info(book_id, headers, gui_callback=None):
    """获取书名、作者、简介、封面URL - 优先使用 cenguigui API"""
    
    def log_message(message, progress=-1):
        """输出日志消息"""
        if gui_callback and len(inspect.signature(gui_callback).parameters) > 1:
            gui_callback(progress, message)
        else:
            with print_lock:
                print(message)

    try:
        # 优先使用 cenguigui API 获取书籍详情
        api = get_tomato_api()
        if api is None:
            return None
        book_details = api.get_book_detail(book_id)
        
        if book_details:
            # 从新API获取书籍信息
            name = book_details.get("book_name", f"未知小说_{book_id}")
            # 如果有别名，可以选择使用别名或主名称
            original_name = book_details.get("original_book_name", name)
            author_name = book_details.get("author", "未知作者")
            description = book_details.get("intro", "无简介")
            cover_url = book_details.get("cover", None)
            
            # 记录获取到的书籍信息（仅在详细日志模式下）
            if CONFIG.get("verbose_logging", False):
                log_message(f"从API获取到书籍信息: 《{name}》")
                if original_name and original_name != name:
                    log_message(f"  别名: {original_name}")
                if author_name and author_name != "未知作者":
                    log_message(f"  作者: {author_name}")
                if description and description != "无简介":
                    desc_preview = description[:100] + "..." if len(description) > 100 else description
                    log_message(f"  简介: {desc_preview}")
                if cover_url:
                    log_message(f"  封面: 已获取")
            
            return name, author_name, description, cover_url
        
        # 如果API失败，尝试从网页获取（作为后备方案）
        url = f'https://fanqienovel.com/page/{book_id}?enter_from=stack-room'
        response = requests.get(url, headers=headers, timeout=CONFIG["request_timeout"])
        if response.status_code != 200:
            error_msg = f"网络请求失败，状态码: {response.status_code}"
            log_message(error_msg)
            return None, None, None, None

        soup = bs4.BeautifulSoup(response.text, 'html.parser')

        # 获取书名 - 尝试多种选择器
        name = "未知书名"
        name_selectors = [
            'h1.info-name',  # 番茄小说新的类名
            'h1',  # 直接查找h1标签
            '.book-title',  # CSS类选择器
            '.page-title',  # 页面标题类
            'h1.title',  # 带title类的h1
            '[data-testid="book-title"]',  # 数据属性选择器
            '.book-name',  # 书籍名称类
            '.novel-title',  # 小说标题类
            'title',  # 页面标题标签
        ]

        for selector in name_selectors:
            if selector.startswith('.'):
                name_element = soup.find(class_=selector[1:])
            elif selector.startswith('['):
                name_element = soup.find(attrs={'data-testid': 'book-title'})
            elif '.' in selector:
                # 处理复合选择器，如 h1.info-name
                tag, class_name = selector.split('.', 1)
                name_element = soup.find(tag, class_=class_name)
            else:
                name_element = soup.find(selector)

            if name_element and name_element.text.strip():
                name = name_element.text.strip()
                # 清理标题中的多余信息
                name = re.sub(r'[-|_].*$', '', name).strip()
                break

        # 获取作者名 - 尝试多种选择器
        author_name = "未知作者"
        author_selectors = [
            '.info-author',  # 番茄小说新的类名
            '.author',  # 番茄小说主要使用这个
            '.author-name',  # 作者名类
            '.author-name .author-name-text',  # 嵌套选择器
            '[data-testid="author-name"]',  # 数据属性
            '.writer',  # 作家类
            '.book-author',  # 书籍作者类
            '.novel-author',  # 小说作者类
            'meta[name="author"]',  # meta标签
        ]

        for selector in author_selectors:
            if selector.startswith('.'):
                author_element = soup.find(class_=selector[1:])
            elif selector.startswith('['):
                author_element = soup.find(attrs={'data-testid': 'author-name'})
            elif selector.startswith('meta'):
                author_element = soup.find('meta', attrs={'name': 'author'})
                if author_element:
                    author_element = author_element.get('content', '')
                    if author_element:
                        author_name = author_element.strip()
                        break
                    continue
            else:
                author_element = soup.find(selector)

            if author_element and author_element.text.strip():
                author_name = author_element.text.strip()
                # 清理作者名中的多余信息
                author_name = re.sub(r'\s*/\s*著', '', author_name).strip()
                break

        # 获取简介 - 尝试多种选择器
        description = "无简介"
        desc_selectors = [
            '.abstract-content-text',  # 番茄小说新的类名
            '.page-abstract-content',  # 番茄小说主要使用这个
            '.page-abstract-content p',  # 简介内容段落
            '.book-description',  # 书籍描述容器
            '.book-description p',  # 书籍描述段落
            '.abstract',  # 摘要容器
            '.abstract p',  # 摘要段落
            '.description',  # 描述容器
            '.description p',  # 描述段落
            '.summary',  # 总结容器
            '.summary p',  # 总结段落
            '.book-intro',  # 书籍介绍
            '.novel-intro',  # 小说介绍
        ]

        for selector in desc_selectors:
            desc_element = soup.select_one(selector)
            if desc_element and desc_element.text.strip():
                description = desc_element.text.strip()
                # 清理简介中的多余空白字符和"作品简介"前缀
                description = re.sub(r'^作品简介\s*', '', description)
                description = re.sub(r'\s+', ' ', description).strip()
                break

        # 获取封面图片URL - 重写逻辑
        cover_url = None

        # 策略1: 从meta标签获取封面（最可靠）
        meta_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            'meta[name="image"]'
        ]

        for selector in meta_selectors:
            meta_element = soup.find('meta', attrs={'property': 'og:image'})
            if not meta_element:
                meta_element = soup.find('meta', attrs={'name': 'twitter:image'})
            if not meta_element:
                meta_element = soup.find('meta', attrs={'name': 'image'})

            if meta_element and meta_element.get('content'):
                potential_url = meta_element.get('content')
                if potential_url and 'http' in potential_url:
                    cover_url = potential_url
                    with print_lock:
                        print(f"从meta标签获取到封面URL: {cover_url}")
                    break

        # 策略2: 智能分析所有图片
        if not cover_url:
            all_imgs = soup.find_all('img')
            cover_candidates = []

            for img in all_imgs:
                img_src = img.get('src', '')
                if not img_src:
                    continue

                # 标准化URL
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                elif img_src.startswith('/'):
                    img_src = 'https://fanqienovel.com' + img_src

                alt_text = img.get('alt', '').lower()
                classes = ' '.join(img.get('class', []))
                parent_classes = ' '.join(img.parent.get('class', [])) if img.parent else ''

                # 计算封面可能性得分
                score = 0

                # 包含novel-pic的URL得分最高
                if 'novel-pic' in img_src:
                    score += 100

                # 包含封面关键词的URL
                if any(keyword in img_src.lower() for keyword in ['cover', 'poster', 'thumb', 'book']):
                    score += 50

                # alt属性包含封面关键词
                if any(keyword in alt_text for keyword in ['封面', 'cover', '书名', '小说', 'book']):
                    score += 30

                # 父元素是封面相关容器
                if any(keyword in parent_classes for keyword in ['book-cover', 'cover', 'poster']):
                    score += 20

                # CSS类名包含封面关键词
                if any(keyword in classes for keyword in ['book-cover', 'cover', 'poster']):
                    score += 15

                # 减分项
                if 'author' in alt_text or 'author-img' in classes:
                    score -= 100  # 作者头像直接排除

                if 'tos-cn-i' in img_src or 'avatar' in img_src.lower():
                    score -= 50  # 头像模式减分

                if any(keyword in img_src.lower() for keyword in ['logo', 'icon', 'default', 'novel-static']):
                    score -= 30  # 明显不是封面的图片

                if score > 10:  # 得分大于10的认为是候选封面
                    cover_candidates.append((img_src, score))

            # 按得分排序，选择得分最高的
            if cover_candidates:
                cover_candidates.sort(key=lambda x: x[1], reverse=True)
                cover_url = cover_candidates[0][0]
                with print_lock:
                    print(f"通过智能分析选择封面URL: {cover_url} (得分: {cover_candidates[0][1]})")

        # 处理相对URL
        if cover_url:
            if cover_url.startswith('//'):
                cover_url = 'https:' + cover_url
            elif cover_url.startswith('/'):
                cover_url = 'https://fanqienovel.com' + cover_url
            
            # 调试：输出选择的封面URL
            with print_lock:
                print(f"选择的封面URL: {cover_url}")

        # 调试信息
        debug_msg = f"获取到书籍信息: 书名='{name}', 作者='{author_name}', 简介长度={len(description)}, 封面URL={'有' if cover_url else '无'}"
        
        if gui_callback and len(inspect.signature(gui_callback).parameters) > 1:
            gui_callback(5, debug_msg)
        else:
            with print_lock:
                print(debug_msg)
        
        # 添加详细调试信息
        with print_lock:
            print(f"详细调试信息:")
            print(f"  - 书名选择器结果: {name}")
            print(f"  - 作者选择器结果: {author_name}")
            print(f"  - 简介选择器结果: {description[:50]}{'...' if len(description) > 50 else ''}")
            print(f"  - 封面选择器结果: {cover_url}")

        return name, author_name, description, cover_url
    except Exception as e:
        error_msg = f"获取书籍信息失败: {str(e)}"
        log_message(error_msg)
        return None, None, None, None


def get_book_cover_url(book_id, headers):
    """尝试从多个来源获取书籍封面URL"""
    cover_url = None
    
    # 方法1: 从网页获取
    try:
        page_url = f'https://fanqienovel.com/page/{book_id}?enter_from=stack-room'
        response = requests.get(page_url, headers=headers, timeout=CONFIG["request_timeout"])
        if response.status_code == 200:
            soup = bs4.BeautifulSoup(response.text, 'html.parser')
            
            # 尝试多种选择器
            cover_selectors = [
                '.page-header img',  # 在page-header容器内的img - 优先级最高
                '.book-cover-img',  # 番茄小说另一种类名
                '.book-cover img',  # 番茄小说主要使用这个
                '.muye-book-cover img',  # 番茄小说另一种类名
                '.novel-cover img', 
                '.book-thumb img',
                '.cover img',
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
                '.book-poster img',
                '.poster img'
            ]
            
            for selector in cover_selectors:
                if selector.endswith('img'):
                    cover_elements = soup.select(selector)
                    for cover_element in cover_elements:
                        if not cover_element:
                            continue

                        # 兼容多种图片地址属性
                        img_src = (
                            cover_element.get('src')
                            or cover_element.get('data-src')
                            or cover_element.get('data-original')
                        )
                        if not img_src:
                            continue

                        # 过滤掉明显不是封面的图片
                        if any(keyword in img_src.lower() for keyword in ['logo', 'icon', 'avatar', 'default', 'user', 'profile', 'novel-static']):
                            continue

                        # 检查alt和class信息
                        alt_text = (cover_element.get('alt') or '').lower()
                        classes = ' '.join(cover_element.get('class') or [])

                        if alt_text and any(keyword in alt_text for keyword in ['封面', 'cover', '书名', '小说', 'book']):
                            cover_url = img_src
                            break

                        # 跳过作者头像
                        if 'author' in alt_text or 'author-img' in classes:
                            continue

                        # 跳过明显是头像的URL模式
                        if 'tos-cn-i' in img_src or 'avatar' in img_src.lower():
                            continue

                        # 优先选择真正的封面URL（包含novel-pic）
                        if 'novel-pic' in img_src:
                            cover_url = img_src
                            break

                        # 如果URL看起来像封面图片，也接受
                        if any(keyword in img_src.lower() for keyword in ['cover', 'poster', 'thumb', 'book', 'fqnovelpic', 'reading-sign']):
                            cover_url = img_src
                            break

                        # 最后的选择：如果前面都没匹配到，使用第一个有效的图片（但排除明显不是封面的）
                        if not cover_url and not any(keyword in img_src.lower() for keyword in ['logo', 'icon', 'avatar', 'novel-static']):
                            cover_url = img_src
                            break

                    if cover_url:
                        break
                            
                elif selector.startswith('meta'):
                    cover_element = soup.find('meta', attrs={'property': 'og:image'})
                    if not cover_element:
                        cover_element = soup.find('meta', attrs={'name': 'twitter:image'})
                    if cover_element and cover_element.get('content'):
                        cover_url = cover_element.get('content')
                        break
                
                if cover_url:
                    break
            
            # 处理相对URL
            if cover_url:
                if cover_url.startswith('//'):
                    cover_url = 'https:' + cover_url
                elif cover_url.startswith('/'):
                    cover_url = 'https://fanqienovel.com' + cover_url
    except Exception as e:
        with print_lock:
            print(f"从网页获取封面失败: {str(e)}")
    
    # 方法2: 尝试从API获取
    if not cover_url:
        try:
            api_url = f"https://fanqienovel.com/api/reader/directory/detail?bookId={book_id}"
            api_response = requests.get(api_url, headers=headers, timeout=CONFIG["request_timeout"])
            if api_response.status_code == 200:
                api_data = api_response.json()
                book_data = api_data.get("data", {}).get("bookInfo", {})
                if book_data:
                    # 优先使用高质量的封面URL
                    cover_url = (book_data.get("posterUrl") or
                               book_data.get("coverUrl") or
                               book_data.get("thumbUrl"))

                    if cover_url:
                        with print_lock:
                            print(f"从API获取到封面URL: {cover_url}")
        except Exception as e:
            with print_lock:
                print(f"从API获取封面失败: {str(e)}")
    
    # 方法3: 尝试从搜索API获取
    if not cover_url:
        try:
            # 先获取书名
            name, _, _, _ = get_book_info(book_id, headers)
            if name and name != "未知书名":
                search_url = "http://fqweb.jsj66.com/search"
                search_params = {"query": name, "page": 1}
                search_response = requests.get(search_url, params=search_params, headers=headers, timeout=10)
                if search_response.status_code == 200:
                    search_data = search_response.json()
                    if search_data.get("data", {}).get("search_tabs"):
                        for tab in search_data["data"]["search_tabs"]:
                            for entry in tab.get("data", []):
                                for book in entry.get("book_data", []):
                                    if book.get("book_id") == book_id or book.get("id") == book_id:
                                        cover_url = book.get("thumb_url") or book.get("cover_url")
                                        break
                                if cover_url:
                                    break
                            if cover_url:
                                break
        except Exception as e:
            with print_lock:
                print(f"从搜索API获取封面失败: {str(e)}")
    
    return cover_url

def create_default_cover(title, author):
    """创建一个简单的默认封面"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # 创建一个400x600的白色背景图片
        width, height = 400, 600
        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)

        try:
            # 尝试使用系统字体
            font_title = ImageFont.truetype("arial.ttf", 30)
            font_author = ImageFont.truetype("arial.ttf", 20)
        except:
            # 如果系统字体不可用，使用默认字体
            font_title = ImageFont.load_default()
            font_author = ImageFont.load_default()

        # 绘制标题
        title_bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        title_y = height // 3

        draw.text((title_x, title_y), title, fill='black', font=font_title)

        # 绘制作者
        author_bbox = draw.textbbox((0, 0), f"作者: {author}", font=font_author)
        author_width = author_bbox[2] - author_bbox[0]
        author_x = (width - author_width) // 2
        author_y = title_y + 100

        draw.text((author_x, author_y), f"作者: {author}", fill='gray', font=font_author)

        # 绘制边框
        draw.rectangle([20, 20, width-20, height-20], outline='black', width=2)

        # 保存到内存缓冲区
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    except ImportError:
        # 如果没有PIL库，返回None
        return None
    except Exception as e:
        with print_lock:
            print(f"创建默认封面失败: {str(e)}")
        return None


def download_and_process_cover(cover_url, headers):
    """下载并处理封面图片
    返回(二进制内容, 扩展名, MIME类型)。尽量转换为通用的JPEG/PNG以保证兼容性。
    """
    if not cover_url:
        return None, None, None
    
    try:
        # 下载封面图片
        cover_response = requests.get(cover_url, headers=headers, timeout=15)
        if cover_response.status_code != 200:
            return None, None, None
        
        # 检测图片格式和大小
        content_type = cover_response.headers.get('content-type', '')
        content_bytes = cover_response.content
        content_length = len(content_bytes)
        
        # 检查图片大小和内容（太小的可能是占位图）
        if content_length < 1000:  # 小于1KB可能是占位图
            with print_lock:
                print(f"封面图片过小 ({content_length} 字节)，跳过")
            return None, None, None

        # 基础魔数检查
        valid_magic = (
            content_bytes.startswith(b'\xff\xd8') or  # JPEG
            content_bytes.startswith(b'\x89PNG') or    # PNG
            content_bytes.startswith(b'GIF8') or        # GIF
            content_bytes.startswith(b'RIFF')           # WEBP/AVI容器
        )
        if not valid_magic:
            with print_lock:
                print("封面图片格式无效，跳过")
            return None, None, None

        # 映射到已知类型
        def infer_type_from_url(url: str):
            lower = url.lower()
            if lower.endswith(('.jpg', '.jpeg')):
                return '.jpg', 'image/jpeg'
            if lower.endswith('.png'):
                return '.png', 'image/png'
            if lower.endswith('.webp'):
                return '.webp', 'image/webp'
            if lower.endswith('.gif'):
                return '.gif', 'image/gif'
            return '.jpg', 'image/jpeg'

        if 'jpeg' in content_type or 'jpg' in content_type:
            file_ext, mime_type = '.jpg', 'image/jpeg'
        elif 'png' in content_type:
            file_ext, mime_type = '.png', 'image/png'
        elif 'gif' in content_type:
            file_ext, mime_type = '.gif', 'image/gif'
        elif 'webp' in content_type or 'heic' in content_type or 'avif' in content_type:
            # 这些格式对很多阅读器不友好，尝试转JPEG
            file_ext, mime_type = '.webp', 'image/webp'
        else:
            file_ext, mime_type = infer_type_from_url(cover_url)

        # 如为WEBP/HEIC/GIF等，尽量转换到JPEG
        needs_convert = mime_type in ('image/webp', 'image/heic', 'image/heif', 'image/avif', 'image/gif')
        if needs_convert:
            try:
                from PIL import Image
                import io
                # 如果是动图，取第一帧
                img = Image.open(io.BytesIO(content_bytes))
                if getattr(img, 'is_animated', False):
                    try:
                        img.seek(0)
                    except Exception:
                        pass
                # 转RGB后保存为JPEG
                img = img.convert('RGB')
                out = io.BytesIO()
                img.save(out, format='JPEG', quality=90)
                content_bytes = out.getvalue()
                file_ext, mime_type = '.jpg', 'image/jpeg'
                with print_lock:
                    print("封面已转换为JPEG以提高兼容性")
            except Exception as convert_err:
                # 转换失败则尽量回退到PNG（若源是PNG/GIF可以再试一次）
                try:
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(content_bytes))
                    img = img.convert('RGB')
                    out = io.BytesIO()
                    img.save(out, format='PNG')
                    content_bytes = out.getvalue()
                    file_ext, mime_type = '.png', 'image/png'
                    with print_lock:
                        print("封面已转换为PNG以提高兼容性")
                except Exception:
                    # 无法转换则仍返回原始内容/类型，可能导致部分阅读器不显示
                    pass

        return content_bytes, file_ext, mime_type
        
    except Exception as e:
        with print_lock:
            print(f"下载封面图片失败: {str(e)}")
        return None, None, None


def load_status(save_path):
    """加载下载状态"""
    status_file = os.path.join(save_path, CONFIG["status_file"])
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
                return set()
        except:
            pass
    return set()


def save_status(save_path, downloaded):
    """保存下载状态"""
    status_file = os.path.join(save_path, CONFIG["status_file"])
    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(list(downloaded), f, ensure_ascii=False, indent=2)


def cleanup_status_file(save_path):
    """清理下载状态文件（chapter.json）"""
    try:
        status_file = os.path.join(save_path, CONFIG["status_file"])
        if os.path.exists(status_file):
            os.remove(status_file)
            with print_lock:
                print(f"已自动清理状态文件: {status_file}")
            return True
        return False
    except Exception as e:
        with print_lock:
            print(f"清理状态文件失败: {str(e)}")
        return False


def create_epub_book(name, author_name, description, chapter_results, chapters, cover_url=None, original_name=None):
    """创建EPUB文件"""
    book = epub.EpubBook()
    book.set_identifier(f'book_{name}_{int(time.time())}')
    book.set_title(name)
    book.set_language('zh-CN')
    book.add_author(author_name)
    book.add_metadata('DC', 'description', description)
    
    # 如果有别名，添加到元数据
    if original_name and original_name != name:
        book.add_metadata('DC', 'alternative', original_name)
    
    # 添加封面图片
    cover_added = False
    if cover_url:
        try:
            # 使用新的封面处理函数
            cover_content, file_ext, mime_type = download_and_process_cover(cover_url, get_headers())
            if cover_content and file_ext and mime_type:
                cover_filename = f'cover{file_ext}'
                # 仅调用set_cover，避免重复清单项
                book.set_cover(cover_filename, cover_content)
                with print_lock:
                    print(f"成功添加封面图片: {cover_filename}")
                cover_added = True
            else:
                with print_lock:
                    print("封面图片下载失败或格式不支持")

        except Exception as e:
            with print_lock:
                print(f"添加封面图片失败: {str(e)}")

    # 如果没有成功添加封面，尝试使用默认封面
    if not cover_added:
        try:
            default_cover = create_default_cover(name, author_name)
            if default_cover:
                book.set_cover('default_cover.png', default_cover)
                with print_lock:
                    print("使用默认封面")
        except Exception as e:
            with print_lock:
                print(f"创建默认封面失败: {str(e)}")

    book.toc = []
    spine = ['nav']

    for idx in range(len(chapters)):
        if idx in chapter_results:
            result = chapter_results[idx]
            # 智能处理标题，避免重复的章节编号
            if result["api_title"]:
                # 检查api_title是否已经包含章节编号，如果是则直接使用
                api_title = result["api_title"].strip()
                base_title = result["base_title"].strip()

                # 如果api_title以"第X章"开头，说明已经包含章节信息，直接使用
                if api_title.startswith("第") and "章" in api_title[:10]:
                    title = api_title
                else:
                    # 如果api_title不包含章节编号，则组合使用
                    title = f'{base_title} {api_title}'
            else:
                title = result["base_title"]
            chapter = epub.EpubHtml(
                title=title,
                file_name=f'chap_{idx}.xhtml',
                lang='zh-CN'
            )
            content = result['content'].replace('\n', '<br/>')
            
            # 如果是第一章，在开头添加作者和简介信息
            if idx == 0:
                # 构建作品信息HTML，包含别名（如果有）
                alias_info = f'<p><strong>别名：</strong>{original_name}</p>' if original_name and original_name != name else ''
                book_info_html = f'''
                <div style="margin-bottom: 30px; padding: 20px; background-color: #f8f9fa; border-left: 4px solid #007bff;">
                    <h2 style="color: #007bff; margin-top: 0;">作品信息</h2>
                    <p><strong>书名：</strong>{name}</p>
                    {alias_info}
                    <p><strong>作者：</strong>{author_name}</p>
                    <p><strong>简介：</strong>{description}</p>
                </div>
                '''
                chapter.content = f'<h1>{title}</h1>{book_info_html}<p>{content}</p>'.encode('utf-8')
            else:
                chapter.content = f'<h1>{title}</h1><p>{content}</p>'.encode('utf-8')
            
            book.add_item(chapter)
            book.toc.append(chapter)
            spine.append(chapter)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    return book


def download_chapters_in_batches(book_id, chapters_to_download, chapter_results, downloaded_ids, pbar, gui_callback=None):
    """顺序批量下载章节（每批最大100章，无并发）。"""
    total_tasks = len(chapters_to_download)
    if total_tasks == 0:
        return

    batch_size = min(30, CONFIG.get("async_batch_size", 30))

    with print_lock:
        print(f"开始批量下载，总章节数: {total_tasks}, 每批最多: {batch_size}")

    completed = 0
    failed_chapters = []
    total_batches = (total_tasks + batch_size - 1) // batch_size or 1

    for start in range(0, total_tasks, batch_size):
        batch = chapters_to_download[start:start + batch_size]
        current_batch = start // batch_size + 1
        item_ids = [ch['id'] for ch in batch]

        api = get_tomato_api()
        if api is None:
            return []
        results = api.get_multi_content(book_id, item_ids) or []
        result_map = {str(item.get('item_id', '')).strip(): item for item in results if item}

        if not result_map:
            failed_chapters.extend(batch)
            with print_lock:
                print(f"批量接口返回为空，批次 {current_batch}/{total_batches}")
            for _ in batch:
                if pbar:
                    pbar.update(1)
            if gui_callback:
                progress = int((completed / total_tasks) * 80) + 10
                gui_callback(progress, f"下载进度 [{current_batch}/{total_batches}]: {completed}/{total_tasks}")
            continue

        for ch in batch:
            chapter_id = str(ch['id'])
            payload = result_map.get(chapter_id)
            if payload:
                content = payload.get('content') or payload.get('text') or ''
                if content:
                    processed = process_chapter_content(content)
                    chapter_results[ch['index']] = {
                        'base_title': ch['title'],
                        'api_title': payload.get('title', ''),
                        'content': processed
                    }
                    downloaded_ids.add(ch['id'])
                    completed += 1
                else:
                    failed_chapters.append(ch)
            else:
                failed_chapters.append(ch)

            if pbar:
                pbar.update(1)

        if gui_callback:
            progress = int((completed / total_tasks) * 80) + 10
            gui_callback(progress, f"下载进度 [{current_batch}/{total_batches}]: {completed}/{total_tasks}")

    if failed_chapters:
        with print_lock:
            print(f"\n批量下载失败章节数: {len(failed_chapters)}，尝试单章兜底...")

        for ch in failed_chapters:
            try:
                api = get_tomato_api()
                if api is None:
                    continue
                data = api.get_content(ch['id'])
                if data and data.get('content'):
                    processed = process_chapter_content(data.get('content', ''))
                    chapter_results[ch['index']] = {
                        'base_title': ch['title'],
                        'api_title': data.get('title', ''),
                        'content': processed
                    }
                    downloaded_ids.add(ch['id'])
                    completed += 1
                    if pbar:
                        pbar.update(1)
            except Exception:
                pass

    if gui_callback:
        progress = int((completed / total_tasks) * 80) + 10
        gui_callback(progress, f"下载完成: {completed}/{total_tasks}")

    with print_lock:
        if failed_chapters:
            final_failed = [ch for ch in failed_chapters if ch['id'] not in downloaded_ids]
            if final_failed:
                print(f"最终有 {len(final_failed)} 个章节下载失败")
        print(f"成功下载 {len(downloaded_ids)} 个章节")


async def download_single_chapter_async(item_id: str) -> Optional[Dict]:
    """异步下载单个章节
    Args:
        item_id: 章节ID
    Returns:
        章节内容字典或None
    """
    try:
        # 使用异步包装同步调用
        loop = asyncio.get_event_loop()
        api = get_tomato_api()
        if api is None:
            return None
        data = await loop.run_in_executor(None, api.get_content, item_id)
        return data
    except Exception:
        return None

async def download_single_chapter(chapter, chapter_results, downloaded_ids, is_retry=False):
    """兼容旧流程的单章下载"""
    try:
        data = await download_single_chapter_async(chapter["id"])
        if data and data.get('content'):
            processed_content = process_chapter_content(data.get('content', ''))
            chapter_results[chapter["index"]] = {
                "base_title": chapter["title"],
                "api_title": data.get("title", ""),
                "content": processed_content
            }
            downloaded_ids.add(chapter["id"])
            return True
        return False
    except Exception:
        return False

def Run(book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, gui_callback=None):
    """运行下载"""

    # 检查章节范围下载功能是否被禁用
    if not CONFIG.get("download_enabled", True) and (start_chapter is not None or end_chapter is not None):
        error_msg = "章节范围下载功能已被禁用。如需启用，请修改config.py中的'download_enabled'设置为True"
        if gui_callback:
            if len(inspect.signature(gui_callback).parameters) > 1:
                gui_callback(-1, error_msg)
            else:
                print(error_msg)
        else:
            print(error_msg)
        return False

    # 日志输出函数，根据是否有GUI回调来选择输出方式
    def log_message(message, progress=-1):
        """输出日志消息"""
        if gui_callback:
            # 检查回调函数的参数数量
            if len(inspect.signature(gui_callback).parameters) > 1:
                gui_callback(progress, message)
            else:
                # 如果是验证码回调，只传递URL参数
                print(message)
        else:
            print(message)

    # 只有在主线程中才设置signal处理
    if threading.current_thread() is threading.main_thread():
        def signal_handler(sig, frame):
            log_message("\n检测到程序中断，正在保存已下载内容...")
            write_downloaded_chapters_in_order()
            save_status(save_path, downloaded)
            log_message(f"已保存 {len(downloaded)} 个章节的进度")
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)

    def write_downloaded_chapters_in_order():
        """按章节顺序写入"""
        if not chapter_results:
            return

        if file_format == 'txt':
            try:
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    # 写入基本信息
                    f.write(f"小说名: {name}\n")
                    # 如果有别名，也写入
                    if original_name and original_name != name:
                        f.write(f"别名: {original_name}\n")
                    f.write(f"作者: {author_name}\n内容简介: {description}\n\n")
                    for idx in range(len(chapters)):
                        if idx in chapter_results:
                            result = chapter_results[idx]
                            # 智能处理标题，避免重复的章节编号
                            if result["api_title"]:
                                # 检查api_title是否已经包含章节编号，如果是则直接使用
                                api_title = result["api_title"].strip()
                                base_title = result["base_title"].strip()

                                # 如果api_title以"第X章"开头，说明已经包含章节信息，直接使用
                                if api_title.startswith("第") and "章" in api_title[:10]:
                                    title = api_title
                                else:
                                    # 如果api_title不包含章节编号，则组合使用
                                    title = f'{base_title} {api_title}'
                            else:
                                title = result["base_title"]
                            f.write(f"{title}\n{result['content']}\n\n")
                log_message(f"下载完成！成功下载 {len(chapter_results)} 个章节，文件已保存到: {output_file_path}")
                # 下载完成后自动清理状态文件
                cleanup_status_file(save_path)
            except Exception as e:
                log_message(f"写入文件失败: {str(e)}")
        elif file_format == 'epub':
            try:
                book = create_epub_book(name, author_name, description, chapter_results, chapters, cover_url, original_name)
                epub.write_epub(output_file_path, book, {})
                log_message(f"下载完成！成功下载 {len(chapter_results)} 个章节，文件已保存到: {output_file_path}")
                # 下载完成后自动清理状态文件
                cleanup_status_file(save_path)
            except Exception as e:
                log_message(f"创建EPUB文件失败: {str(e)}")

    try:
        headers = get_headers()
        try:
            chapters = get_chapters_from_api(book_id, headers)
        except Exception as e:
            error_msg = f"获取章节列表失败: {str(e)}"
            log_message(error_msg)
            return False

        if not chapters:
            error_msg = "未找到任何章节，请检查小说ID是否正确。"
            log_message(error_msg)
            return False

        # 获取书籍信息，包括别名
        book_info = get_book_info(book_id, headers, gui_callback)
        if book_info and book_info[0]:
            name, author_name, description, cover_url = book_info
        else:
            name = f"未知小说_{book_id}"
            author_name = "未知作者"
            description = "无简介"
            cover_url = None
        
        # 获取别名信息（沿用番茄API详情）
        original_name = None
        try:
            api = get_tomato_api()
            if api is None:
                return None
            details_for_alias = api.get_book_detail(book_id)
            if details_for_alias:
                original_name = details_for_alias.get("original_book_name", name)
        except Exception:
            original_name = None
        
        # 如果没有获取到封面URL，尝试其他方法
        if not cover_url:
            try:
                # 尝试使用专门的封面获取函数
                backup_cover_url = get_book_cover_url(book_id, headers)
                if backup_cover_url:
                    cover_url = backup_cover_url
                    log_message(f"通过备用方法获取到封面URL: {cover_url}")
            except Exception as e:
                log_message(f"获取封面URL失败: {str(e)}")
                cover_url = None

        # 处理章节范围选择
        if start_chapter is not None and end_chapter is not None:
            if start_chapter < 0:
                start_chapter = 0
            if end_chapter >= len(chapters):
                end_chapter = len(chapters) - 1
            chapters = chapters[start_chapter:end_chapter + 1]

        downloaded = load_status(save_path)
        todo_chapters = [ch for ch in chapters if ch["id"] not in downloaded]

        if not todo_chapters:
            log_message("所有章节已是最新，无需下载")
            return True

        log_message(f"开始下载：《{name}》, 总章节数: {len(chapters)}, 待下载: {len(todo_chapters)}")
        os.makedirs(save_path, exist_ok=True)

        output_file_path = os.path.join(save_path, f"{name}.{file_format}")
        if file_format == 'txt' and not os.path.exists(output_file_path):
            with open(output_file_path, 'w', encoding='utf-8') as f:
                # 写入基本信息
                f.write(f"小说名: {name}\n")
                # 如果有别名，也写入
                if original_name and original_name != name:
                    f.write(f"别名: {original_name}\n")
                f.write(f"作者: {author_name}\n内容简介: {description}\n\n")

        success_count = 0
        failed_chapters = []
        chapter_results = {}
        lock = threading.Lock()

        # 批量下载模式（顺序处理，每批最多100章）
        if todo_chapters:
            log_message(f"开始批量下载，共 {len(todo_chapters)} 个章节...")
            disable_tqdm = gui_callback is not None
            with tqdm(total=len(todo_chapters), desc="下载进度", disable=disable_tqdm) as pbar:
                download_chapters_in_batches(book_id, todo_chapters, chapter_results, downloaded, pbar, gui_callback)
            
            success_count = len(chapter_results)
            write_downloaded_chapters_in_order()
            save_status(save_path, downloaded)

        if success_count > 0:
            log_message(f"下载完成！成功下载 {success_count} 个章节")
            # 最终下载完成后清理状态文件
            cleanup_status_file(save_path)
            return True
        else:
            log_message("下载失败：未能下载任何章节")
            return False

    except Exception as e:
        log_message(f"运行错误: {str(e)}")
        if 'downloaded' in locals():
            write_downloaded_chapters_in_order()
            save_status(save_path, downloaded)
            # 即使出错，如果已经下载了内容，也清理状态文件
            if chapter_results:
                cleanup_status_file(save_path)
        return False


def main():
    print("""欢迎使用番茄小说下载器 v2.0.0
开发者：POf-L
Github：https://github.com/POf-L/Fanqie-novel-Downloader
*使用前须知*：
    开始下载之后，请耐心等待小说下载完成再查看文件！
    如果遇到"所有章节已是最新"的提示，请删除chapter.json后重试。
------------------------------------------""")

    print("正在测试API连接...")
    manager = get_api_manager()
    if manager is None or not manager.test_connection():
        print("API连接失败，请检查网络连接！")
        return
    
    print("API连接成功！")

    while True:
        book_id = input("请输入小说ID (输入q退出)：").strip()
        if book_id.lower() == 'q':
            break

        save_path = input("保存路径 (留空为当前目录)：").strip() or os.getcwd()

        file_format = input("请选择下载格式 (1:txt, 2:epub)：").strip()
        if file_format == '1':
            file_format = 'txt'
        elif file_format == '2':
            file_format = 'epub'
        else:
            print("无效的格式选择，将默认使用txt格式")
            file_format = 'txt'

        try:
            Run(book_id, save_path, file_format)
        except Exception as e:
            print(f"运行错误: {str(e)}")

        print("\n" + "="*50 + "\n")


# GUI兼容性类
class NovelDownloaderAPI:
    """GUI兼容的API类"""

    def __init__(self, gui_callback=None):
        self.gui_verification_callback = gui_callback
        self.current_progress_callback = None
        self.enhanced_downloader = self  # 指向自己以保持兼容性
        self.is_cancelled = False  # 下载取消状态
        self.progress_callback = None  # 进度回调

    def initialize_api(self):
        """初始化API，测试连接"""
        # 优先测试番茄API连接，失败则回退测试旧聚合API
        ok = False
        try:
            api = get_tomato_api()
            if api:
                ok = api.test_connection()
            else:
                ok = False
        except Exception:
            ok = False
        if not ok:
            try:
                manager = get_api_manager()
                if manager:
                    ok = manager.test_connection()
                else:
                    ok = False
            except Exception:
                ok = False
        if self.gui_verification_callback and len(inspect.signature(self.gui_verification_callback).parameters) > 1:
            self.gui_verification_callback(10 if ok else -1, "API连接成功" if ok else "API连接失败，请检查网络")
        return ok

    def search_novels(self, keyword, offset=0, tab_type=1):
        """搜索小说 - 接入 cenguigui 番茄 API"""
        try:
            api = get_tomato_api()
            if api is None:
                return None
            search_results = api.search(keyword, offset=offset or 0)
            if search_results:
                items = []
                books = search_results.get("books", [])
                for book in books:
                    items.append({
                        "book_id": book.get("book_id", ""),
                        "book_name": book.get("book_name", ""),
                        "author": book.get("author", "未知作者"),
                        "category": book.get("category", ""),
                        "abstract": book.get("intro", ""),
                        "score": book.get("score", ""),
                        "serial_count": book.get("chapter_count", ""),
                        "word_number": book.get("word_count", ""),
                        "thumb_url": book.get("cover", ""),
                        "creation_status": book.get("status", ""),
                        "tags": book.get("tags", []),
                        "sub_info": "",
                        "tomato_book_status": book.get("status", ""),
                        "source": "api"
                    })
                return {
                    "success": True,
                    "data": {
                        "items": items,
                        "has_more": False,
                        "next_offset": offset + len(items),
                        "search_keyword": keyword,
                        "source": "api"
                    }
                }
            return {"success": False, "data": {"items": [], "has_more": False, "next_offset": offset}}
        except Exception as e:
            with print_lock:
                print(f"搜索异常: {str(e)}")
            return {"success": False, "data": {"items": [], "has_more": False, "next_offset": offset}}

    def get_novel_info(self, book_id):
        """获取小说信息"""
        try:
            headers = get_headers()
            name, author, description, cover_url = get_book_info(book_id, headers)

            if name:
                return {
                    'isSuccess': True,
                    'data': {
                        'data': {
                            'book_id': book_id,
                            'book_name': name,
                            'author': author,
                            'abstract': description,
                            'cover_url': cover_url,
                            'source': '番茄小说'
                        },
                        'enhanced': False
                    }
                }
            else:
                return {
                    'isSuccess': False,
                    'data': {'data': {}}
                }
        except Exception as e:
            return {
                'isSuccess': False,
                'data': {'data': {}}
            }

    def get_book_details(self, book_id):
        """获取书籍详细信息（与get_novel_info相同）"""
        return self.get_novel_info(book_id)

    def set_progress_callback(self, callback):
        """设置进度回调"""
        self.current_progress_callback = callback
        self.progress_callback = callback  # 也设置这个属性以保持兼容性
    
    def cancel_download(self):
        """取消下载"""
        self.is_cancelled = True

    def run_download(self, book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, gui_callback=None):
        """运行下载（兼容GUI调用）"""
        try:
            # 检查章节范围下载功能是否被禁用
            if not CONFIG.get("download_enabled", True) and (start_chapter is not None or end_chapter is not None):
                error_msg = "章节范围下载功能已被禁用。如需启用，请修改config.py中的'download_enabled'设置为True"
                if self.current_progress_callback:
                    self.current_progress_callback(-1, error_msg)
                elif gui_callback:
                    gui_callback(-1, error_msg)
                else:
                    print(error_msg)
                return False

            # 如果有GUI回调，使用它
            if gui_callback:
                self.gui_verification_callback = gui_callback

            # 新API不需要检查api_endpoints
            # API管理器会自动处理连接

            # 调用主下载函数，传递章节范围参数和GUI回调
            result = Run(book_id, save_path, file_format, start_chapter, end_chapter, self.current_progress_callback)

            # 如果有进度回调，报告最终结果
            if self.current_progress_callback and result:
                self.current_progress_callback(100, "下载完成！")
            elif self.current_progress_callback and not result:
                self.current_progress_callback(-1, "下载失败")

            return result
        except Exception as e:
            error_msg = f"下载错误: {str(e)}"
            print(error_msg)
            if self.current_progress_callback:
                self.current_progress_callback(-1, error_msg)
            return False


# 重复的函数定义已删除，保留第872行的正确版本

if __name__ == "__main__":
    main()
