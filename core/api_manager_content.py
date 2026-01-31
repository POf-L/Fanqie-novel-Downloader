# -*- coding: utf-8 -*-
"""
APIManager 内容获取相关方法 - 从 api_manager.py 拆分
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Dict, List, Optional

import aiohttp
import requests

from config.config import CONFIG, print_lock, get_headers


class APIManagerContentMixin:
    """章节内容/整书内容"""

    def get_chapter_content(self, item_id: str) -> Optional[Dict]:
        self.ensure_base_url()
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
            from utils.async_logger import safe_print
            safe_print(f"获取章节内容异常: {str(e)}")
            return None
    async def get_chapter_content_async(self, item_id: str) -> Optional[Dict]:
        """获取章节内容(异步)
        优先使用 /api/chapter 简化接口，失败时回退到 /api/content
        使用令牌桶算法实现真正的并发速率限制
        """
        max_retries = CONFIG.get("max_retries", 3)
        session = await self._get_async_session()
        state = self._get_async_state()
        semaphore = state.get('semaphore')
        rate_limiter = state.get('rate_limiter')

        # 使用令牌桶进行速率限制，允许真正的并发
        async with semaphore:
            if rate_limiter:
                await rate_limiter.acquire()

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
    def get_full_content(self, book_id: str) -> Optional[str]:
        self.ensure_base_url(require_full_download=True)
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

        # 尝试导入节点缓存（web_app模块可能未加载）
        try:
            from web.web_app import PROBED_NODES_CACHE
        except ImportError:
            PROBED_NODES_CACHE = {}

        def _is_node_available(url: str) -> bool:
            """检查节点是否可用（启动时探测通过）"""
            url = (url or "").strip().rstrip('/')
            if not PROBED_NODES_CACHE:
                return True  # 缓存为空时默认可用
            if url not in PROBED_NODES_CACHE:
                return True  # 未探测的节点默认可用
            return PROBED_NODES_CACHE[url].get('available', False)

        def _supports_full_download(url: str) -> bool:
            """检查节点是否支持整本下载"""
            url = (url or "").strip().rstrip('/')
            if not PROBED_NODES_CACHE:
                return True  # 缓存为空时默认支持
            if url not in PROBED_NODES_CACHE:
                return True  # 未探测的节点默认支持
            return PROBED_NODES_CACHE[url].get('supports_full_download', True)

        # 构建要尝试的节点列表（优先当前 base_url，跳过不可用和不支持整本下载的节点）
        urls_to_try: List[str] = []
        if self.base_url and _is_node_available(self.base_url) and _supports_full_download(self.base_url):
            urls_to_try.append(self.base_url)
        for source in api_sources:
            base = ""
            supports_full = True
            if isinstance(source, dict):
                base = source.get("base_url", "") or source.get("api_base_url", "")
                supports_full = source.get("supports_full_download", True)
            elif isinstance(source, str):
                base = source
            base = (base or "").strip().rstrip('/')
            if base and base not in urls_to_try:
                # 跳过不支持整本下载的节点
                if not supports_full:
                    with print_lock:
                        print(f"[DEBUG] 跳过不支持整本下载的节点: {base}")
                    continue
                # 跳过启动时探测失败的节点
                if not _is_node_available(base):
                    with print_lock:
                        print(f"[DEBUG] 跳过不可用节点: {base}")
                    continue
                urls_to_try.append(base)

        if not urls_to_try:
            with print_lock:
                print("[DEBUG] 没有可用的支持整本下载的节点")
            return None

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
            print(f"获取整书内容异常: 所有节点均失败")
        return None

