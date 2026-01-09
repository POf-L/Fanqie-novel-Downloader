# -*- coding: utf-8 -*-
"""
番茄小说下载器核心模块 - 对接官方API https://qkfqapi.vv9v.cn/docs
"""

import time
import requests
import re
import os
import json
import urllib3
import threading
import signal
import sys
import inspect
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
from tqdm import tqdm
from typing import Optional, Dict, List, Union
from ebooklib import epub
from config import CONFIG, print_lock, get_headers
import aiohttp
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from watermark import apply_watermark_to_chapter
from locales import t

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

# ===================== 官方API管理器 =====================

class APIManager:
    """番茄小说官方API统一管理器 - https://qkfqapi.vv9v.cn/docs
    支持同步和异步两种调用方式
    """
    
    def __init__(self):
        # 优先使用已选择的 api_base_url；否则回退到 api_sources 第一个
        preferred_base_url = (CONFIG.get("api_base_url") or "").strip().rstrip('/')
        if preferred_base_url:
            self.base_url = preferred_base_url
        else:
            api_sources = CONFIG.get("api_sources", [])
            base_url = ""
            if api_sources and isinstance(api_sources, list) and len(api_sources) > 0:
                first = api_sources[0]
                if isinstance(first, dict):
                    base_url = first.get("base_url") or first.get("api_base_url") or ""
                elif isinstance(first, str):
                    base_url = first
            self.base_url = (base_url or "").strip().rstrip('/')
        self.endpoints = CONFIG["endpoints"]
        self._tls = threading.local()
        self._async_session: Optional[aiohttp.ClientSession] = None
        self.semaphore = None
        self.last_request_time = 0
        self.request_lock = asyncio.Lock()

    def _get_session(self) -> requests.Session:
        """获取同步HTTP会话"""
        sess = getattr(self._tls, 'session', None)
        if sess is None:
            sess = requests.Session()
            retries = Retry(
                total=CONFIG.get("max_retries", 3),
                backoff_factor=0.3,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET", "POST"),
                raise_on_status=False,
            )
            pool_size = CONFIG.get("connection_pool_size", 10)
            adapter = HTTPAdapter(
                pool_connections=pool_size, 
                pool_maxsize=pool_size, 
                max_retries=retries,
                pool_block=False
            )
            sess.mount('http://', adapter)
            sess.mount('https://', adapter)
            sess.headers.update({'Connection': 'keep-alive'})
            self._tls.session = sess
        return sess

    async def _get_async_session(self) -> aiohttp.ClientSession:
        """获取异步HTTP会话"""
        if self._async_session is None or self._async_session.closed:
            timeout = aiohttp.ClientTimeout(total=CONFIG["request_timeout"], connect=5, sock_read=15)
            connector = aiohttp.TCPConnector(
                limit=CONFIG.get("connection_pool_size", 10),
                limit_per_host=CONFIG.get("connection_pool_size", 10),
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                force_close=False,
                keepalive_timeout=30
            )
            self._async_session = aiohttp.ClientSession(
                headers=get_headers(), 
                timeout=timeout, 
                connector=connector,
                trust_env=True
            )
            self.semaphore = asyncio.Semaphore(CONFIG.get("max_workers", 5))
        return self._async_session

    async def close_async(self):
        """关闭异步会话"""
        if self._async_session:
            await self._async_session.close()
    
    def search_books(self, keyword: str, offset: int = 0) -> Optional[Dict]:
        """搜索书籍"""
        try:
            url = f"{self.base_url}{self.endpoints['search']}"
            params = {"key": keyword, "tab_type": "3", "offset": str(offset)}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return data
            return None
        except Exception as e:
            with print_lock:
                print(t("dl_search_error", str(e)))
            return None
    
    def get_book_detail(self, book_id: str) -> Optional[Dict]:
        """获取书籍详情，返回 dict 或 None，如果书籍下架会返回 {'_error': 'BOOK_REMOVE'}"""
        try:
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
            with print_lock:
                print(t("dl_detail_error", str(e)))
            return None
    
    def get_directory(self, book_id: str) -> Optional[List[Dict]]:
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
        """获取章节列表"""
        try:
            with print_lock:
                print(t("dl_chapter_list_start", book_id))
                
            url = f"{self.base_url}{self.endpoints['book']}"
            params = {"book_id": book_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            with print_lock:
                print(t("dl_chapter_list_resp", response.status_code))
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    level1_data = data["data"]
                    if isinstance(level1_data, dict) and "data" in level1_data:
                        return level1_data["data"]
                    return level1_data
            return None
        except Exception as e:
            with print_lock:
                print(t("dl_chapter_list_error", str(e)))
            return None
    
    def get_chapter_content(self, item_id: str) -> Optional[Dict]:
        """获取章节内容(同步)
        优先使用 /api/chapter 简化接口，失败时回退到 /api/content
        """
        try:
            # 优先尝试简化的 /api/chapter 接口（更稳定）
            chapter_endpoint = self.endpoints.get('chapter', '/api/chapter')
            url = f"{self.base_url}{chapter_endpoint}"
            params = {"item_id": item_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    return data["data"]
            
            # 回退到 /api/content 接口
            url = f"{self.base_url}{self.endpoints['content']}"
            params = {"tab": "小说", "item_id": item_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 and "data" in data:
                    return data["data"]
            return None
        except Exception as e:
            with print_lock:
                print(t("dl_content_error", str(e)))
            return None


    async def get_chapter_content_async(self, item_id: str) -> Optional[Dict]:
        """获取章节内容(异步)
        优先使用 /api/chapter 简化接口，失败时回退到 /api/content
        """
        max_retries = CONFIG.get("max_retries", 3)
        
        async with self.semaphore:
            async with self.request_lock:
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                if time_since_last < CONFIG.get("download_delay", 0.5):
                    await asyncio.sleep(CONFIG.get("download_delay", 0.5) - time_since_last)
                self.last_request_time = time.time()
            
            session = await self._get_async_session()
            
            # 优先尝试简化的 /api/chapter 接口
            chapter_endpoint = self.endpoints.get('chapter', '/api/chapter')
            url = f"{self.base_url}{chapter_endpoint}"
            params = {"item_id": item_id}
            
            for attempt in range(max_retries):
                try:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("code") == 200 and "data" in data:
                                return data["data"]
                        elif response.status == 429:
                            await asyncio.sleep(min(2 ** attempt, 10))
                            continue
                        break  # 其他错误，尝试备用接口
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(CONFIG.get("retry_delay", 2) * (attempt + 1))
                        continue
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.3)
                        continue
                    break
            
            # 回退到 /api/content 接口
            url = f"{self.base_url}{self.endpoints['content']}"
            params = {"tab": "小说", "item_id": item_id}
            
            for attempt in range(max_retries):
                try:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("code") == 200 and "data" in data:
                                return data["data"]
                        elif response.status == 429:
                            await asyncio.sleep(min(2 ** attempt, 10))
                            continue
                        return None
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(CONFIG.get("retry_delay", 2) * (attempt + 1))
                        continue
                    return None
                except Exception:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.3)
                        continue
                    return None
            
            return None

    def get_full_content(self, book_id: str) -> Optional[Union[str, Dict[str, str]]]:
        """获取整本小说内容，支持多节点自动切换

        返回：
        - dict: 批量模式返回的 {item_id: content}（最可靠，可与目录按 item_id 精准对齐）
        - str: 文本模式返回的整本内容（兼容旧接口/节点）
        """
        max_retries = max(1, int(CONFIG.get("max_retries", 3) or 3))
        api_sources = CONFIG.get("api_sources", [])

        def _extract_bulk_map(payload) -> Optional[Dict[str, str]]:
            if not isinstance(payload, dict):
                return None
            nested = payload.get('data')
            if not isinstance(nested, dict):
                return None

            keys = list(nested.keys())
            if not keys:
                return None

            sample = keys[:min(5, len(keys))]
            if not all(str(k).isdigit() for k in sample):
                return None

            result: Dict[str, str] = {}
            for k, v in nested.items():
                item_id = str(k)
                content = None
                if isinstance(v, str):
                    content = v
                elif isinstance(v, dict):
                    content = (
                        v.get("content")
                        or v.get("text")
                        or v.get("raw")
                        or v.get("raw_text")
                        or ""
                    )
                if isinstance(content, str) and content.strip():
                    result[item_id] = content

            return result or None

        def _extract_text(payload) -> Optional[str]:
            if isinstance(payload, str):
                return payload
            if isinstance(payload, dict):
                nested = payload.get('data')
                if isinstance(nested, str):
                    return nested
                if isinstance(nested, dict):
                    for key in ("content", "text", "raw", "raw_text", "full_text"):
                        val = nested.get(key)
                        if isinstance(val, str):
                            return val
                for key in ("content", "text", "raw", "raw_text", "full_text"):
                    val = payload.get(key)
                    if isinstance(val, str):
                        return val
            return None

        endpoint = self.endpoints.get('content')
        if not endpoint:
            return None

        # 构建要尝试的节点列表（优先当前 base_url）
        urls_to_try: List[str] = []
        if self.base_url:
            urls_to_try.append(self.base_url)
        for source in api_sources:
            base = ""
            if isinstance(source, dict):
                base = source.get("base_url", "") or source.get("api_base_url", "")
            elif isinstance(source, str):
                base = source
            base = (base or "").strip().rstrip('/')
            if base and base not in urls_to_try:
                urls_to_try.append(base)

        # 下载模式：批量模式优先（可按 item_id 对齐）
        download_modes = [
            {"tab": "批量", "book_id": book_id},
            {"tab": "下载", "book_id": book_id},
        ]

        headers = get_headers()
        headers['Connection'] = 'close'

        session = self._get_session()
        connect_timeout = 10
        read_timeout = max(120, int((CONFIG.get("request_timeout", 30) or 30) * 10))
        timeout = (connect_timeout, read_timeout)

        transient_errors = (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ContentDecodingError,
        )

        for base_url in urls_to_try:
            url = f"{base_url}{endpoint}"

            for mode in download_modes:
                for attempt in range(max_retries):
                    try:
                        with print_lock:
                            print(
                                f"[DEBUG] 尝试节点 {base_url}, 模式 tab={mode.get('tab')} "
                                f"({attempt + 1}/{max_retries})"
                            )

                        with session.get(
                            url,
                            params=mode,
                            headers=headers,
                            timeout=timeout,
                            stream=True,
                        ) as response:
                            status_code = response.status_code
                            resp_headers = dict(response.headers)
                            resp_encoding = response.encoding

                            if status_code == 400:
                                # 该节点不支持此模式，尝试下一个模式
                                break
                            if status_code != 200:
                                # 429/5xx 交给会话重试；这里额外做少量退避
                                if status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                                    time.sleep(min(2 ** attempt, 10))
                                    continue
                                break

                            raw_buf = bytearray()
                            for chunk in response.iter_content(chunk_size=131072):
                                if chunk:
                                    raw_buf.extend(chunk)
                            raw_content = bytes(raw_buf)

                        if len(raw_content) < 1000:
                            break

                        content_type = (resp_headers.get('content-type') or '').lower()
                        is_json_like = 'application/json' in content_type or raw_content[:1] in (b'{', b'[')

                        if is_json_like:
                            try:
                                data = json.loads(raw_content.decode('utf-8', errors='ignore'))
                            except Exception:
                                data = None

                            if not data:
                                if attempt < max_retries - 1:
                                    time.sleep(min(2 ** attempt, 10))
                                    continue
                                break

                            bulk_map = _extract_bulk_map(data)
                            if bulk_map:
                                with print_lock:
                                    print(f"[DEBUG] 急速下载成功，节点: {base_url}, 模式: tab={mode.get('tab')}")
                                return bulk_map

                            text_from_json = _extract_text(data)
                            if text_from_json and len(text_from_json) > 1000:
                                with print_lock:
                                    print(f"[DEBUG] 急速下载成功，节点: {base_url}, 模式: tab={mode.get('tab')}")
                                return text_from_json

                            break

                        encoding = resp_encoding or 'utf-8'
                        text = raw_content.decode(encoding, errors='replace')
                        if len(text) > 1000:
                            with print_lock:
                                print(f"[DEBUG] 急速下载成功，节点: {base_url}, 模式: tab={mode.get('tab')}")
                            return text

                        break

                    except transient_errors as e:
                        if attempt < max_retries - 1:
                            time.sleep(min(2 ** attempt, 10))
                            continue
                        with print_lock:
                            print(
                                f"[DEBUG] 节点 {base_url} 下载失败: {type(e).__name__}，"
                                f"切换模式/节点"
                            )
                    except Exception as e:
                        with print_lock:
                            print(f"[DEBUG] 节点 {base_url} 异常: {type(e).__name__}")
                        break

        with print_lock:
            print(t("dl_full_content_error", "所有节点均失败"))
        return None

def _normalize_title(title: str) -> str:
    """标准化章节标题，用于模糊匹配"""
    # 移除空格
    s = re.sub(r'\s+', '', title)
    # 统一标点：中文逗号、顿号、点号统一
    s = re.sub(r'[,，、．.·]', '', s)
    # 阿拉伯数字转中文数字的映射（用于比较）
    return s.lower()


def _extract_title_core(title: str) -> str:
    """提取标题核心部分（去掉章节号前缀）"""
    # 移除 "第x章"、"数字、"、"数字." 等前缀
    s = re.sub(r'^(第[0-9一二三四五六七八九十百千]+章[、,，\s]*)', '', title)
    s = re.sub(r'^(\d+[、,，.\s]+)', '', s)
    return s.strip()


def parse_novel_text_with_catalog(text: str, catalog: List[Dict]) -> List[Dict]:
    """使用目录接口的章节标题来分割整本小说内容
    
    Args:
        text: 整本小说的纯文本内容
        catalog: 目录接口返回的章节列表 [{'title': '...', 'id': '...', 'index': ...}, ...]
    
    Returns:
        带内容的章节列表 [{'title': '...', 'id': '...', 'index': ..., 'content': '...'}, ...]
    """
    if not catalog:
        return []
    
    def escape_for_regex(s: str) -> str:
        return re.escape(s)
    
    def find_title_in_text(title: str, search_text: str, start_offset: int = 0) -> Optional[tuple]:
        """在文本中查找标题，返回 (match_start, match_end) 或 None"""
        # 1. 精确匹配
        pattern = re.compile(r'^[ \t]*' + escape_for_regex(title) + r'[ \t]*$', re.MULTILINE)
        match = pattern.search(search_text)
        if match:
            return (start_offset + match.start(), start_offset + match.end())
        
        # 2. 模糊匹配：提取标题核心部分
        title_core = _extract_title_core(title)
        if title_core and len(title_core) >= 2:
            # 匹配包含核心标题的行
            pattern = re.compile(r'^[^\n]*' + escape_for_regex(title_core) + r'[^\n]*$', re.MULTILINE)
            match = pattern.search(search_text)
            if match:
                return (start_offset + match.start(), start_offset + match.end())
        
        return None
    
    # 查找每个章节标题在文本中的位置
    chapter_positions = []
    for ch in catalog:
        title = ch['title']
        result = find_title_in_text(title, text)
        if result:
            chapter_positions.append({
                'title': title,
                'id': ch.get('id', ''),
                'index': ch['index'],
                'line_start': result[0],  # 标题行开始位置
                'start': result[1]        # 内容开始位置（标题行之后）
            })
    
    if not chapter_positions:
        return []
    
    # 按位置排序
    chapter_positions.sort(key=lambda x: x['line_start'])
    
    # 提取每章内容
    chapters = []
    for i, pos in enumerate(chapter_positions):
        if i + 1 < len(chapter_positions):
            end = chapter_positions[i + 1]['line_start']
        else:
            end = len(text)
        
        content = text[pos['start']:end].strip()
        chapters.append({
            'title': pos['title'],
            'id': pos['id'],
            'index': pos['index'],
            'content': content
        })
    
    # 按原始目录顺序重新排序
    chapters.sort(key=lambda x: x['index'])
    
    return chapters


def parse_novel_text(text: str) -> List[Dict]:
    """解析整本小说文本，分离章节（无目录时的降级方案）"""
    lines = text.splitlines()
    chapters = []
    
    current_chapter = None
    current_content = []
    
    # 匹配常见章节格式
    chapter_pattern = re.compile(
        r'^\s*('
        r'第[0-9一二三四五六七八九十百千]+章'  # 第x章
        r'|[0-9]+[\.、,，]\s*\S'                # 1、标题 1.标题
        r')\s*.*',
        re.UNICODE
    )
    
    for line in lines:
        match = chapter_pattern.match(line)
        if match:
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content)
                chapters.append(current_chapter)
            
            title = line.strip()
            current_chapter = {
                'title': title,
                'id': str(len(chapters)),
                'index': len(chapters)
            }
            current_content = []
        else:
            if current_chapter:
                current_content.append(line)
    
    if current_chapter:
        current_chapter['content'] = '\n'.join(current_content)
        chapters.append(current_chapter)
    
    return chapters


# 全局API管理器实例
api_manager = None

def get_api_manager():
    """获取API管理器实例"""
    global api_manager
    if api_manager is None:
        api_manager = APIManager()
    return api_manager


# ===================== 辅助函数 =====================

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


def _get_status_file_path(book_id: str) -> str:
    """获取下载状态文件路径（保存在临时目录，不污染小说目录）"""
    import tempfile
    # 使用 book_id 的哈希作为文件名，避免冲突
    status_dir = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader')
    os.makedirs(status_dir, exist_ok=True)
    filename = f".download_status_{book_id}.json"
    return os.path.join(status_dir, filename)


def _get_content_file_path(book_id: str) -> str:
    """获取已下载内容文件路径"""
    import tempfile
    status_dir = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader')
    os.makedirs(status_dir, exist_ok=True)
    filename = f".download_content_{book_id}.json"
    return os.path.join(status_dir, filename)


def load_status(book_id: str):
    """加载下载状态（从临时目录读取）"""
    status_file = _get_status_file_path(book_id)
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except:
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
        except:
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
            print(t("dl_save_status_fail", str(e)))


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
    except:
        pass


def has_saved_state(book_id: str) -> bool:
    """检查是否有已保存的下载状态
    
    Args:
        book_id: 书籍ID
    
    Returns:
        bool: 是否有已保存的状态
    """
    status_file = _get_status_file_path(book_id)
    content_file = _get_content_file_path(book_id)
    return os.path.exists(status_file) or os.path.exists(content_file)


def analyze_download_completeness(chapter_results: dict, expected_chapters: list = None, log_func=None) -> dict:
    """
    分析下载完整性
    
    Args:
        chapter_results: 已下载的章节结果 {index: {'title': ..., 'content': ...}}
        expected_chapters: 期望的章节列表 [{'id': ..., 'title': ..., 'index': ...}]
        log_func: 日志输出函数
    
    Returns:
        分析结果字典:
        - total_expected: 期望总章节数
        - total_downloaded: 已下载章节数
        - missing_indices: 缺失的章节索引列表
        - order_correct: 顺序是否正确
        - completeness_percent: 完整度百分比
    """
    def log(msg, progress=-1):
        if log_func:
            log_func(msg, progress)
        else:
            print(msg)
    
    result = {
        'total_expected': 0,
        'total_downloaded': len(chapter_results),
        'missing_indices': [],
        'order_correct': True,
        'completeness_percent': 100.0
    }
    
    if not chapter_results:
        log(t("dl_analyze_no_chapters"))
        result['completeness_percent'] = 0
        return result
    
    # 获取已下载的章节索引
    downloaded_indices = set(chapter_results.keys())
    
    # 如果有期望的章节列表，进行完整性比对
    if expected_chapters:
        expected_indices = set(ch['index'] for ch in expected_chapters)
        result['total_expected'] = len(expected_indices)
        
        # 查找缺失的章节
        missing_indices = expected_indices - downloaded_indices
        result['missing_indices'] = sorted(list(missing_indices))
        
        if missing_indices:
            missing_count = len(missing_indices)
            log(t("dl_analyze_summary", len(expected_indices), len(downloaded_indices), missing_count))
            
            # 显示部分缺失章节信息
            if missing_count <= 10:
                missing_titles = []
                for ch in expected_chapters:
                    if ch['index'] in missing_indices:
                        missing_titles.append(f"{t('dl_chapter_title', ch['index']+1)}: {ch['title']}")
                log(t("dl_analyze_missing", ', '.join(missing_titles[:5])))
        else:
            log(t("dl_analyze_pass", len(expected_indices)))
    else:
        # 没有期望列表，使用已下载内容分析
        result['total_expected'] = len(chapter_results)
        
        # 检查索引是否连续
        sorted_indices = sorted(downloaded_indices)
        if sorted_indices:
            min_idx, max_idx = sorted_indices[0], sorted_indices[-1]
            expected_range = set(range(min_idx, max_idx + 1))
            missing_in_range = expected_range - downloaded_indices
            
            if missing_in_range:
                result['missing_indices'] = sorted(list(missing_in_range))
                log(t("dl_analyze_gap", sorted(missing_in_range)[:10]))
    
    # 验证章节顺序（检查标题中的章节号是否递增）
    sorted_results = sorted(chapter_results.items(), key=lambda x: x[0])
    order_issues = []
    
    for i in range(1, len(sorted_results)):
        prev_idx, prev_data = sorted_results[i-1]
        curr_idx, curr_data = sorted_results[i]
        
        # 检查索引是否连续
        if curr_idx != prev_idx + 1:
            order_issues.append({
                'type': 'gap',
                'from_index': prev_idx,
                'to_index': curr_idx,
                'gap': curr_idx - prev_idx - 1
            })
    
    if order_issues:
        result['order_correct'] = False
        total_gaps = sum(issue['gap'] for issue in order_issues)
        log(t("dl_analyze_order_fail", len(order_issues), total_gaps))
    else:
        log(t("dl_analyze_order_pass"))
    
    # 计算完整度
    if result['total_expected'] > 0:
        result['completeness_percent'] = (result['total_downloaded'] / result['total_expected']) * 100
    
    return result


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
            print(t("dl_cover_fail", str(e)))
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
                print(t("dl_cover_add_fail", str(e)))
    
    spine_items = ['nav']
    toc_items = []
    
    # 创建书籍信息页 (简介页)
    intro_html = f'<h1>{name}</h1>'
    if author_name:
        intro_html += f'<p><strong>作者：</strong> {author_name}</p>'
    
    if description:
        intro_html += '<hr/>'
        intro_html += f'<h3>{t("dl_intro_title")}</h3>'
        # 处理简介的换行
        desc_lines = description.split('\n')
        for line in desc_lines:
            if line.strip():
                intro_html += f'<p>{line.strip()}</p>'
                
    intro_chapter = epub.EpubHtml(title=t('dl_book_detail_title'), file_name='intro.xhtml', lang='zh-CN')
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
            f.write(f"{t('label_author')}{author_name}\n")
        if description:
            f.write(f"\n{t('dl_intro_title')}:\n{description}\n")
        f.write("\n" + "="*50 + "\n\n")
        
        for ch_data in chapters:
            title = ch_data.get('title', '')
            content = ch_data.get('content', '')
            f.write(f"\n{title}\n\n")
            f.write(f"{content}\n\n")
    
    return txt_path


def Run(book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, selected_chapters=None, gui_callback=None):
    """运行下载"""
    
    api = get_api_manager()
    if api is None:
        return False
    
    def log_message(message, progress=-1):
        if gui_callback and len(inspect.signature(gui_callback).parameters) > 1:
            gui_callback(progress, message)
        else:
            print(message)
    
    try:
        log_message(t("dl_fetching_info"), 5)
        book_detail = api.get_book_detail(book_id)
        if not book_detail:
            log_message(t("dl_fetch_info_fail"))
            return False
        
        name = book_detail.get("book_name", f"未知小说_{book_id}")
        author_name = book_detail.get("author", t("dl_unknown_author"))
        description = book_detail.get("abstract", "")
        cover_url = book_detail.get("thumb_url", "")
        
        log_message(t("dl_book_info_log", name, author_name), 10)
        
        chapter_results = {}
        use_full_download = False
        speed_mode_downloaded_ids = set()
        
        # 先获取章节目录（优先使用 directory 接口，更快且标题与整本下载一致）
        log_message("正在获取章节列表...", 15)
        chapters = []
        
        # 优先尝试 directory 接口
        directory_data = api.get_directory(book_id)
        if directory_data:
            for idx, ch in enumerate(directory_data):
                item_id = ch.get("item_id")
                title = ch.get("title", f"第{idx+1}章")
                if item_id:
                    chapters.append({"id": str(item_id), "title": title, "index": idx})
        
        # 降级到 book 接口
        if not chapters:
            chapters_data = api.get_chapter_list(book_id)
            if chapters_data:
                if isinstance(chapters_data, dict):
                    all_item_ids = chapters_data.get("allItemIds", [])
                    chapter_list = chapters_data.get("chapterListWithVolume", [])
                    
                    if chapter_list:
                        idx = 0
                        for volume in chapter_list:
                            if isinstance(volume, list):
                                for ch in volume:
                                    if isinstance(ch, dict):
                                        item_id = ch.get("itemId") or ch.get("item_id")
                                        title = ch.get("title", f"第{idx+1}章")
                                        if item_id:
                                            chapters.append({"id": str(item_id), "title": title, "index": idx})
                                            idx += 1
                    else:
                        for idx, item_id in enumerate(all_item_ids):
                            chapters.append({"id": str(item_id), "title": f"第{idx+1}章", "index": idx})
                elif isinstance(chapters_data, list):
                    for idx, ch in enumerate(chapters_data):
                        item_id = ch.get("item_id") or ch.get("chapter_id")
                        title = ch.get("title", f"第{idx+1}章")
                        if item_id:
                            chapters.append({"id": str(item_id), "title": title, "index": idx})
        
        if not chapters:
            log_message(t("dl_fetch_list_fail"))
            return False
        
        total_chapters = len(chapters)
        log_message(t("dl_found_chapters", total_chapters), 20)
        
        # 尝试极速下载模式 (仅当没有指定范围且没有选择特定章节时)
        if start_chapter is None and end_chapter is None and not selected_chapters:
            log_message(t("dl_try_speed_mode"), 25)
            full_content = api.get_full_content(book_id)
            if full_content:
                log_message(t("dl_speed_mode_success"), 30)
                # 批量模式：返回 {item_id: content}，可精准与目录对齐
                if isinstance(full_content, dict):
                    with tqdm(total=len(chapters), desc=t("dl_processing_chapters"), disable=gui_callback is not None) as pbar:
                        for ch in chapters:
                            raw = full_content.get(ch['id'])
                            if isinstance(raw, str) and raw.strip():
                                processed = process_chapter_content(raw)
                                chapter_results[ch['index']] = {
                                    'title': ch['title'],
                                    'content': processed
                                }
                                speed_mode_downloaded_ids.add(ch['id'])
                            if pbar:
                                pbar.update(1)

                    parsed_count = len(speed_mode_downloaded_ids)
                    log_message(t("dl_speed_mode_parsed", parsed_count), 50)

                    if parsed_count == total_chapters:
                        use_full_download = True
                        log_message(t("dl_process_complete"), 80)
                    else:
                        log_message(f"急速模式批量内容不完整 ({parsed_count}/{total_chapters})，将缺失章节切换到普通模式下载")
                else:
                    full_text = str(full_content)
                    # 使用目录标题来分割内容（兼容旧节点/下载模式）
                    chapters_parsed = parse_novel_text_with_catalog(full_text, chapters)

                    if chapters_parsed and len(chapters_parsed) >= len(chapters) * 0.8:
                        # 成功解析出至少80%的章节
                        log_message(t("dl_speed_mode_parsed", len(chapters_parsed)), 50)
                        with tqdm(total=len(chapters_parsed), desc=t("dl_processing_chapters"), disable=gui_callback is not None) as pbar:
                            for ch in chapters_parsed:
                                processed = process_chapter_content(ch['content'])
                                chapter_results[ch['index']] = {
                                    'title': ch['title'],
                                    'content': processed
                                }
                                if pbar:
                                    pbar.update(1)

                        use_full_download = True
                        log_message(t("dl_process_complete"), 80)
                    else:
                        parsed_count = len(chapters_parsed) if chapters_parsed else 0
                        log_message(f"急速模式解析不完整 ({parsed_count}/{total_chapters})，切换到普通模式")
            else:
                log_message(t("dl_speed_mode_fail"))

        # 如果没有使用极速模式，则走普通模式
        if not use_full_download:
            
            if not chapters:
                log_message(t("dl_no_chapters_found"))
                return False
            
            total_chapters = len(chapters)
            log_message(t("dl_found_chapters", total_chapters), 20)
            
            if start_chapter is not None or end_chapter is not None:
                start_idx = (start_chapter - 1) if start_chapter else 0
                end_idx = end_chapter if end_chapter else total_chapters
                chapters = chapters[start_idx:end_idx]
                log_message(t("dl_range_log", start_idx+1, end_idx))
            
            if selected_chapters:
                try:
                    selected_indices = set(int(x) for x in selected_chapters)
                    chapters = [ch for ch in chapters if ch['index'] in selected_indices]
                    log_message(t("dl_selected_log", len(chapters)))
                except Exception as e:
                    log_message(t("dl_filter_error", e))
            
            downloaded_ids = load_status(book_id)
            if speed_mode_downloaded_ids:
                downloaded_ids.update(speed_mode_downloaded_ids)
             
            # 加载已保存的章节内容（断点续传）
            saved_content = load_saved_content(book_id)
            if saved_content:
                log_message(f"发现已保存的下载进度，已有 {len(saved_content)} 个章节", 22)
                chapter_results.update(saved_content)
            
            chapters_to_download = [ch for ch in chapters if ch["id"] not in downloaded_ids]
            
            if not chapters_to_download:
                log_message(t("dl_all_downloaded"))
            else:
                log_message(t("dl_start_download_log", len(chapters_to_download)), 25)
            
            completed = 0
            total_tasks = len(chapters_to_download)
            
            with tqdm(total=total_tasks, desc=t("dl_progress_desc"), disable=gui_callback is not None) as pbar:
                with ThreadPoolExecutor(max_workers=CONFIG.get("max_workers", 5)) as executor:
                    future_to_chapter = {
                        executor.submit(api.get_chapter_content, ch["id"]): ch
                        for ch in chapters_to_download
                    }
                    
                    for future in as_completed(future_to_chapter):
                        ch = future_to_chapter[future]
                        try:
                            data = future.result()
                            if data and data.get('content'):
                                processed = process_chapter_content(data.get('content', ''))
                                chapter_results[ch['index']] = {
                                    'title': ch['title'],
                                    'content': processed
                                }
                                downloaded_ids.add(ch['id'])
                                completed += 1
                                if pbar:
                                    pbar.update(1)
                                if gui_callback:
                                    progress = int((completed / total_tasks) * 60) + 25
                                    gui_callback(progress, t("dl_progress_log", completed, total_tasks))
                        except Exception:
                            pass
            
            # 保存下载状态和章节内容
            save_status(book_id, downloaded_ids)
            save_content(book_id, chapter_results)
        
        # ==================== 下载完整性分析 ====================
        if gui_callback:
            gui_callback(85, t("dl_analyzing_completeness"))
        else:
            log_message(t("dl_analyzing_completeness"), 85)
        
        # 分析结果
        analysis_result = analyze_download_completeness(
            chapter_results, 
            chapters if not use_full_download else None,
            log_message
        )
        
        # 如果有缺失章节，尝试补充下载
        if analysis_result['missing_indices'] and not use_full_download:
            missing_count = len(analysis_result['missing_indices'])
            log_message(t("dl_missing_retry", missing_count), 87)
            
            # 获取缺失章节的信息
            missing_chapters = [ch for ch in chapters if ch['index'] in analysis_result['missing_indices']]
            
            # 补充下载缺失章节（最多重试3次）
            for retry in range(3):
                if not missing_chapters:
                    break
                    
                log_message(t("dl_retry_log", retry + 1, len(missing_chapters)), 88)
                still_missing = []
                
                for ch in missing_chapters:
                    try:
                        data = api.get_chapter_content(ch["id"])
                        if data and data.get('content'):
                            processed = process_chapter_content(data.get('content', ''))
                            chapter_results[ch['index']] = {
                                'title': ch['title'],
                                'content': processed
                            }
                            downloaded_ids.add(ch['id'])
                        else:
                            still_missing.append(ch)
                    except Exception:
                        still_missing.append(ch)
                    time.sleep(0.5)  # 避免请求过快
                
                missing_chapters = still_missing
                if not missing_chapters:
                    log_message(t("dl_retry_success"), 90)
                    break
            
            # 更新状态
            save_status(book_id, downloaded_ids)
            
            # 最终检查
            if missing_chapters:
                missing_indices = [ch['index'] + 1 for ch in missing_chapters]
                log_message(t("dl_retry_fail", len(missing_chapters), missing_indices[:10]), 90)
        
        # 验证章节顺序（使用 ChapterOrderValidator）
        if gui_callback:
            gui_callback(92, t("dl_verifying_order"))
        
        # 创建验证器实例
        order_validator = ChapterOrderValidator(chapters)
        
        # 验证顺序
        validation_result = order_validator.validate_order(chapter_results)
        sequential_result = order_validator.verify_sequential(chapter_results)
        
        if not validation_result['is_valid']:
            if validation_result['gaps']:
                log_message(f"检测到缺失章节: {len(validation_result['gaps'])} 个", 93)
            if validation_result['out_of_order']:
                issues_preview = validation_result['out_of_order'][:5]
                log_message(f"检测到章节序号不连续: {issues_preview}{'...' if len(validation_result['out_of_order']) > 5 else ''}", 93)
        else:
            log_message("章节顺序验证通过", 93)
        
        # 使用验证器排序章节
        sorted_chapters = order_validator.sort_chapters(chapter_results)
        
        # 最终统计
        total_expected = len(chapters) if not use_full_download else len(chapter_results)
        total_downloaded = len(chapter_results)
        completeness = (total_downloaded / total_expected * 100) if total_expected > 0 else 100
        
        log_message(f"下载统计: {total_downloaded}/{total_expected} 章 ({completeness:.1f}%)", 95)
        
        if gui_callback:
            gui_callback(95, "正在生成文件...")
        
        if file_format == 'epub':
            output_file = create_epub(name, author_name, description, cover_url, sorted_chapters, save_path)
        else:
            output_file = create_txt(name, author_name, description, sorted_chapters, save_path)
        
        # 下载完成后清除临时状态文件
        clear_status(book_id)
        
        # 最终结果
        if completeness >= 100:
            log_message(f"下载完成! 文件: {output_file}", 100)
        else:
            log_message(f"下载完成(部分章节缺失)! 文件: {output_file}", 100)
        
        return True
        
    except Exception as e:
        log_message(f"下载失败: {str(e)}")
        return False


# ===================== 章节顺序验证器 =====================

class ChapterOrderValidator:
    """验证和修复章节顺序
    
    确保下载的章节按正确顺序排列，检测缺失和重复
    """
    
    def __init__(self, expected_chapters: List[dict]):
        """
        Args:
            expected_chapters: 期望的章节列表 [{'id': str, 'title': str, 'index': int}, ...]
        """
        self.expected_chapters = expected_chapters
        self.chapter_map = {str(ch.get('id', ch.get('item_id', ''))): ch.get('index', i) 
                          for i, ch in enumerate(expected_chapters)}
        self.index_to_chapter = {ch.get('index', i): ch for i, ch in enumerate(expected_chapters)}
    
    def validate_order(self, chapter_results: dict) -> dict:
        """
        验证章节顺序
        
        Args:
            chapter_results: 下载结果 {index: {'title': str, 'content': str}, ...}
        
        Returns:
            {
                'is_valid': bool,
                'gaps': List[int],      # 缺失的章节索引
                'out_of_order': List[tuple],  # 顺序错误的章节对
                'duplicates': List[int]  # 重复的章节索引
            }
        """
        result = {
            'is_valid': True,
            'gaps': [],
            'out_of_order': [],
            'duplicates': []
        }
        
        if not chapter_results:
            return result
        
        # 获取所有索引并排序
        indices = sorted(chapter_results.keys())
        
        if not indices:
            return result
        
        # 检查缺失的章节（在期望范围内）
        expected_indices = set(range(len(self.expected_chapters)))
        downloaded_indices = set(indices)
        result['gaps'] = sorted(list(expected_indices - downloaded_indices))
        
        # 检查顺序是否正确（索引应该是连续递增的）
        for i in range(1, len(indices)):
            if indices[i] != indices[i-1] + 1:
                # 发现不连续
                result['out_of_order'].append((indices[i-1], indices[i]))
        
        # 检查是否有效
        if result['gaps'] or result['out_of_order'] or result['duplicates']:
            result['is_valid'] = False
        
        return result
    
    def sort_chapters(self, chapter_results: dict) -> List[dict]:
        """
        按正确顺序排序章节

        Args:
            chapter_results: 下载结果 {index: {'title': str, 'content': str}, ...}

        Returns:
            排序后的章节列表 [{'index': int, 'title': str, 'content': str}, ...]
        """
        sorted_chapters = []

        # 确保 key 是整数类型后排序
        int_keys = []
        for k in chapter_results.keys():
            try:
                int_keys.append(int(k))
            except (ValueError, TypeError):
                # 如果无法转换为整数，跳过
                continue

        int_keys.sort()

        for index in int_keys:
            chapter_data = chapter_results.get(index) or chapter_results.get(str(index))
            if chapter_data:
                sorted_chapters.append({
                    'index': index,
                    'title': chapter_data.get('title', f'第{index + 1}章'),
                    'content': chapter_data.get('content', '')
                })

        return sorted_chapters
    
    def map_bulk_content(self, bulk_data: dict, item_ids: List[str]) -> dict:
        """
        将批量下载内容映射到正确的章节索引
        
        Args:
            bulk_data: 批量下载的原始数据 {item_id: content, ...}
            item_ids: 章节ID列表（按目录顺序）
        
        Returns:
            映射后的结果 {index: {'title': str, 'content': str}, ...}
        """
        result = {}
        
        for idx, item_id in enumerate(item_ids):
            item_id_str = str(item_id)
            if item_id_str in bulk_data:
                content_data = bulk_data[item_id_str]
                if isinstance(content_data, dict):
                    result[idx] = {
                        'title': content_data.get('title', f'第{idx + 1}章'),
                        'content': content_data.get('content', '')
                    }
                else:
                    result[idx] = {
                        'title': f'第{idx + 1}章',
                        'content': str(content_data)
                    }
        
        return result
    
    def verify_sequential(self, chapter_results: dict) -> dict:
        """
        验证章节索引是否连续无间隙
        
        Args:
            chapter_results: 下载结果
        
        Returns:
            {
                'is_sequential': bool,
                'missing_count': int,
                'missing_indices': List[int]
            }
        """
        if not chapter_results:
            return {'is_sequential': True, 'missing_count': 0, 'missing_indices': []}
        
        indices = sorted(chapter_results.keys())
        min_idx, max_idx = indices[0], indices[-1]
        
        expected_set = set(range(min_idx, max_idx + 1))
        actual_set = set(indices)
        missing = sorted(list(expected_set - actual_set))
        
        return {
            'is_sequential': len(missing) == 0,
            'missing_count': len(missing),
            'missing_indices': missing
        }
    
    def map_text_parsed_content(self, parsed_chapters: List[dict], catalog: List[dict]) -> dict:
        """
        将文本解析模式的章节内容映射到正确的索引
        
        使用目录中的章节标题来匹配解析出的章节，确保顺序正确
        
        Args:
            parsed_chapters: 解析出的章节列表 [{'title': str, 'content': str}, ...]
            catalog: 目录章节列表 [{'id': str, 'title': str, 'index': int}, ...]
        
        Returns:
            映射后的结果 {index: {'title': str, 'content': str}, ...}
        """
        result = {}
        
        # 构建标题到目录索引的映射
        title_to_index = {}
        for ch in catalog:
            # 标准化标题（去除空白、统一格式）
            normalized_title = ch.get('title', '').strip()
            title_to_index[normalized_title] = ch.get('index', 0)
        
        # 映射解析出的章节
        for parsed_ch in parsed_chapters:
            parsed_title = parsed_ch.get('title', '').strip()
            
            # 尝试精确匹配
            if parsed_title in title_to_index:
                idx = title_to_index[parsed_title]
                result[idx] = {
                    'title': parsed_title,
                    'content': parsed_ch.get('content', '')
                }
            else:
                # 尝试模糊匹配（去除标点符号和空格）
                import re
                clean_parsed = re.sub(r'[\s\u3000]+', '', parsed_title)
                for cat_title, idx in title_to_index.items():
                    clean_cat = re.sub(r'[\s\u3000]+', '', cat_title)
                    if clean_parsed == clean_cat:
                        result[idx] = {
                            'title': cat_title,  # 使用目录中的标准标题
                            'content': parsed_ch.get('content', '')
                        }
                        break
        
        return result
    
    def get_validation_summary(self, chapter_results: dict) -> str:
        """
        获取验证结果的摘要信息
        
        Args:
            chapter_results: 下载结果
        
        Returns:
            摘要字符串
        """
        validation = self.validate_order(chapter_results)
        sequential = self.verify_sequential(chapter_results)
        
        lines = []
        
        if validation['is_valid'] and sequential['is_sequential']:
            lines.append("✓ 章节顺序验证通过")
        else:
            if validation['gaps']:
                lines.append(f"⚠ 缺失章节: {len(validation['gaps'])} 个")
            if validation['out_of_order']:
                lines.append(f"⚠ 顺序异常: {len(validation['out_of_order'])} 处")
            if sequential['missing_indices']:
                lines.append(f"⚠ 索引不连续: 缺失 {sequential['missing_count']} 个")
        
        return '\n'.join(lines) if lines else "章节顺序正常"


class NovelDownloader:
    """小说下载器类"""
    
    def __init__(self):
        self.is_cancelled = False
        self.current_progress_callback = None
        self.gui_verification_callback = None
    
    def cancel_download(self):
        """取消下载"""
        self.is_cancelled = True
    
    def run_download(self, book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, selected_chapters=None, gui_callback=None):
        """运行下载"""
        try:
            if gui_callback:
                self.gui_verification_callback = gui_callback
            
            return Run(book_id, save_path, file_format, start_chapter, end_chapter, selected_chapters, gui_callback)
        except Exception as e:
            print(f"下载失败: {str(e)}")
            return False
    
    def search_novels(self, keyword, offset=0):
        """搜索小说"""
        try:
            api = get_api_manager()
            if api is None:
                return None
            
            search_results = api.search_books(keyword, offset)
            if search_results and search_results.get("data"):
                return search_results["data"]
            return None
        except Exception as e:
            with print_lock:
                print(t("dl_search_fail", str(e)))
            return None


downloader_instance = NovelDownloader()


class BatchDownloader:
    """批量下载器"""
    
    def __init__(self):
        self.is_cancelled = False
        self.results = []  # 下载结果列表
        self.current_index = 0
        self.total_count = 0
    
    def cancel(self):
        """取消批量下载"""
        self.is_cancelled = True
    
    def reset(self):
        """重置状态"""
        self.is_cancelled = False
        self.results = []
        self.current_index = 0
        self.total_count = 0
    
    def run_batch(self, book_ids: list, save_path: str, file_format: str = 'txt', 
                  progress_callback=None, delay_between_books: float = 2.0):
        """
        批量下载多本书籍
        
        Args:
            book_ids: 书籍ID列表
            save_path: 保存路径
            file_format: 文件格式 ('txt' 或 'epub')
            progress_callback: 进度回调函数 (current, total, book_name, status, message)
            delay_between_books: 每本书之间的延迟（秒）
        
        Returns:
            dict: 批量下载结果
        """
        self.reset()
        self.total_count = len(book_ids)
        
        if not book_ids:
            return {'success': False, 'message': t('dl_batch_no_books'), 'results': []}
        
        api = get_api_manager()
        if api is None:
            return {'success': False, 'message': t('dl_batch_api_fail'), 'results': []}
        
        def log(msg):
            print(msg)
        
        log(t("dl_batch_start", self.total_count))
        log("=" * 50)
        
        for idx, book_id in enumerate(book_ids):
            if self.is_cancelled:
                log(t("dl_batch_cancelled"))
                break
            
            self.current_index = idx + 1
            book_id = str(book_id).strip()
            
            # 获取书籍信息
            book_name = f"书籍_{book_id}"
            try:
                book_detail = api.get_book_detail(book_id)
                if book_detail:
                    book_name = book_detail.get('book_name', book_name)
            except:
                pass
            
            log("\n" + t("dl_batch_downloading", self.current_index, self.total_count, book_name))
            
            if progress_callback:
                progress_callback(self.current_index, self.total_count, book_name, 'downloading', t("dl_batch_progress", self.current_index))
            
            # 执行下载
            result = {
                'book_id': book_id,
                'book_name': book_name,
                'success': False,
                'message': ''
            }
            
            try:
                # 创建单本书的进度回调
                def single_book_callback(progress, message):
                    if progress_callback:
                        overall_progress = ((self.current_index - 1) / self.total_count * 100) + (progress / self.total_count)
                        progress_callback(self.current_index, self.total_count, book_name, 'downloading', message)
                
                success = Run(book_id, save_path, file_format, gui_callback=single_book_callback)
                
                if success:
                    result['success'] = True
                    result['message'] = '下载成功'
                    log(t("dl_batch_success", book_name))
                else:
                    result['message'] = '下载失败'
                    log(t("dl_batch_fail", book_name))
                    
            except Exception as e:
                result['message'] = str(e)
                log(t("dl_batch_exception", book_name, str(e)))
            
            self.results.append(result)
            
            if progress_callback:
                status = 'success' if result['success'] else 'failed'
                progress_callback(self.current_index, self.total_count, book_name, status, result['message'])
            
            # 延迟，避免请求过快
            if idx < len(book_ids) - 1 and not self.is_cancelled:
                time.sleep(delay_between_books)
        
        # 统计结果
        success_count = sum(1 for r in self.results if r['success'])
        failed_count = len(self.results) - success_count
        
        log("\n" + "=" * 50)
        log(t("dl_batch_summary"))
        log(t("dl_batch_stats_success", success_count))
        log(t("dl_batch_stats_fail", failed_count))
        log(t("dl_batch_stats_total", len(self.results)))
        
        if failed_count > 0:
            log("\n" + t("dl_batch_fail_list"))
            for r in self.results:
                if not r['success']:
                    log(f"   - 《{r['book_name']}》: {r['message']}")
        
        return {
            'success': failed_count == 0,
            'message': t("dl_batch_complete", success_count, len(self.results)),
            'total': len(self.results),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': self.results
        }


batch_downloader = BatchDownloader()


def signal_handler(sig, frame):
    """信号处理"""
    print('\n正在取消下载...')
    downloader_instance.cancel_download()
    batch_downloader.cancel()
    sys.exit(0)


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGINT, signal_handler)
    except ValueError:
        pass
    
    print("番茄小说下载器")
    print("="*50)
    print("1. 单本下载")
    print("2. 批量下载")
    mode = input("选择模式 (1/2, 默认: 1): ").strip() or "1"
    
    save_path = input("请输入保存路径(默认: ./novels): ").strip() or "./novels"
    file_format = input("选择格式 (txt/epub, 默认: txt): ").strip() or "txt"
    os.makedirs(save_path, exist_ok=True)
    
    if mode == "2":
        # 批量下载模式
        print("\n请输入书籍ID列表（每行一个，输入空行结束）:")
        book_ids = []
        while True:
            line = input().strip()
            if not line:
                break
            # 支持逗号/空格/换行分隔
            for bid in re.split(r'[,\s]+', line):
                bid = bid.strip()
                if bid:
                    book_ids.append(bid)
        
        if book_ids:
            print(f"\n共 {len(book_ids)} 本书籍待下载")
            result = batch_downloader.run_batch(book_ids, save_path, file_format)
            print(f"\n批量下载结束: {result['message']}")
        else:
            print("没有输入书籍ID")
    else:
        # 单本下载模式
        book_id = input("请输入书籍ID: ").strip()
        success = Run(book_id, save_path, file_format)
        if success:
            print("下载完成!")
        else:
            print("下载失败!")
