# -*- coding: utf-8 -*-
"""
APIManager 核心（会话/限速/初始化）- 从 api_manager.py 拆分
"""

from __future__ import annotations

import time
import requests
import threading
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, List, Tuple

from config.config import CONFIG, print_lock, get_headers


class TokenBucket:
    """令牌桶算法实现并发速率限制，允许真正的并发请求"""

    def __init__(self, rate: float, capacity: int):
        """
        rate: 每秒生成的令牌数
        capacity: 桶的最大容量
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取一个令牌，如果没有则等待（优化版：移除递归调用）"""
        while True:
            async with self._lock:
                now = time.time()
                # 补充令牌
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return

                # 计算需要等待的时间
                wait_time = (1 - self.tokens) / self.rate

            # 在锁外等待
            await asyncio.sleep(wait_time)


class APIManagerCoreMixin:
    """会话与初始化"""

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
        # 使用令牌桶替代全局锁，允许真正的并发
        self.rate_limiter: Optional[TokenBucket] = None
        # 预初始化异步会话以减少启动延迟
        self._session_initialized = False
        self._init_lock = asyncio.Lock()
        self._base_url_verified_at = 0.0
        self._base_url_verification_ttl = 60.0
        self._base_url_last_error = None
    def _normalize_base_url(self, url: str) -> str:
        return (url or "").strip().rstrip('/')

    def _get_candidate_base_urls(self) -> List[Tuple[str, bool]]:
        urls: List[Tuple[str, bool]] = []

        try:
            current = self._normalize_base_url(getattr(self, "base_url", ""))
            if current:
                urls.append((current, True))
        except Exception:
            pass

        sources = []
        try:
            sources = CONFIG.get("api_sources", []) or []
        except Exception:
            sources = []

        for s in sources:
            base = ""
            supports_full = True
            if isinstance(s, dict):
                base = s.get("base_url") or s.get("api_base_url") or ""
                if "supports_full_download" in s:
                    supports_full = bool(s.get("supports_full_download"))
            elif isinstance(s, str):
                base = s

            base = self._normalize_base_url(base)
            if not base:
                continue
            if any(u == base for u, _ in urls):
                continue
            urls.append((base, supports_full))

        return urls

    def _probe_base_url(self, base_url: str, timeout: float) -> Tuple[bool, int, str]:
        start = time.perf_counter()
        try:
            endpoint = (self.endpoints or {}).get("search") or "/api/search"
            url = f"{base_url}{endpoint}"
            params = {"key": "test", "tab_type": "3", "offset": "0"}

            with requests.Session() as sess:
                sess.trust_env = bool(CONFIG.get("use_system_proxy", False))
                resp = sess.get(url, params=params, headers=get_headers(), timeout=timeout)

            latency_ms = int((time.perf_counter() - start) * 1000)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None

                if isinstance(data, dict) and data.get("code") == 200:
                    return True, latency_ms, ""

            return False, latency_ms, f"status={resp.status_code}"
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return False, latency_ms, str(e)

    def ensure_base_url(self, force: bool = False, require_full_download: bool = False) -> str:
        now = time.time()

        base_url = self._normalize_base_url(getattr(self, "base_url", ""))
        verified_at = float(getattr(self, "_base_url_verified_at", 0.0) or 0.0)
        ttl = float(getattr(self, "_base_url_verification_ttl", 60.0) or 60.0)

        if not force and base_url and (now - verified_at) < ttl:
            return base_url

        candidates = self._get_candidate_base_urls()
        if not candidates:
            return base_url

        probe_timeout = min(2.5, float(CONFIG.get("request_timeout", 30) or 30))

        if base_url:
            ok, _, _ = self._probe_base_url(base_url, timeout=min(1.5, probe_timeout))
            if ok:
                self._base_url_verified_at = now
                self._base_url_last_error = None
                return base_url

        results = []
        with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as ex:
            fut_map = {ex.submit(self._probe_base_url, url, probe_timeout): (url, supports_full) for url, supports_full in candidates}
            for fut in as_completed(fut_map):
                url, supports_full = fut_map[fut]
                try:
                    ok, latency_ms, err = fut.result()
                except Exception as e:
                    ok, latency_ms, err = False, 999999, str(e)
                results.append((ok, supports_full, latency_ms, url, err))

        available = [r for r in results if r[0]]
        if require_full_download:
            available_full = [r for r in available if r[1]]
            if available_full:
                available = available_full

        if available:
            available.sort(key=lambda x: (not x[1], x[2]))
            best_url = available[0][3]
            self.base_url = best_url
            try:
                CONFIG["api_base_url"] = best_url
            except Exception:
                pass
            self._base_url_verified_at = now
            self._base_url_last_error = None
            return best_url

        self._base_url_verified_at = now
        self._base_url_last_error = "no_available_nodes"
        return base_url

    def _get_session(self) -> requests.Session:
        """获取同步HTTP会话"""
        sess = getattr(self._tls, 'session', None)
        if sess is None:
            sess = requests.Session()
            sess.trust_env = bool(CONFIG.get("use_system_proxy", False))
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
    def _get_async_state(self) -> dict:
        """获取线程局部的异步会话状态（避免跨线程/跨事件循环共享 aiohttp 会话）"""
        state = getattr(self._tls, 'async_state', None)
        if state is None:
            state = {
                'session': None,
                'initialized': False,
                'init_lock': asyncio.Lock(),
                'semaphore': None,
                'rate_limiter': None,
            }
            self._tls.async_state = state
        return state
    async def _get_async_session(self) -> aiohttp.ClientSession:
        """获取异步HTTP会话 - 优化版：减少重复初始化"""
        state = self._get_async_state()
        session = state.get('session')
        if state.get('initialized') and session and not session.closed:
            return session

        init_lock = state.get('init_lock')
        async with init_lock:
            # 双重检查锁定模式（线程局部）
            session = state.get('session')
            if state.get('initialized') and session and not session.closed:
                return session

            # 优化连接参数以减少初始化时间
            timeout = aiohttp.ClientTimeout(
                total=CONFIG["request_timeout"],
                connect=3,  # 减少连接超时
                sock_read=10  # 减少读取超时
            )
            connector = aiohttp.TCPConnector(
                limit=CONFIG.get("connection_pool_size", 200),
                limit_per_host=min(CONFIG.get("max_workers", 30) * 3, 100),  # 增加每主机连接数
                ttl_dns_cache=600,  # 增加DNS缓存时间
                enable_cleanup_closed=True,
                force_close=False,
                keepalive_timeout=60,  # 增加keepalive时间
                use_dns_cache=True  # 启用DNS缓存
            )
            session = aiohttp.ClientSession(
                headers=get_headers(),
                timeout=timeout,
                connector=connector,
                trust_env=bool(CONFIG.get("use_system_proxy", False))
            )
            semaphore = asyncio.Semaphore(CONFIG.get("max_workers", 30))
            # 优化令牌桶参数：提高突发处理能力
            rate = CONFIG.get("api_rate_limit", 50)
            capacity = max(CONFIG.get("max_workers", 30), rate)  # 容量至少等于速率
            rate_limiter = TokenBucket(rate=rate, capacity=capacity)

            state['session'] = session
            state['semaphore'] = semaphore
            state['rate_limiter'] = rate_limiter
            state['initialized'] = True

            # 兼容：保留旧字段，但不再作为共享状态使用
            self._async_session = session
            self.semaphore = semaphore
            self.rate_limiter = rate_limiter
            self._session_initialized = True

        return session
    async def close_async(self):
        """关闭异步会话"""
        state = getattr(self._tls, 'async_state', None)
        if state:
            session = state.get('session')
            if session and not session.closed:
                await session.close()
            state['session'] = None
            state['semaphore'] = None
            state['rate_limiter'] = None
            state['initialized'] = False

        # 兼容：同步旧字段（仅反映当前线程状态）
        if self._async_session and not self._async_session.closed:
            await self._async_session.close()
        self._async_session = None
        self.semaphore = None
        self.rate_limiter = None
        self._session_initialized = False
    async def pre_initialize(self):
        """预初始化异步会话，减少首次调用延迟"""
        try:
            await self._get_async_session()
            from utils.async_logger import safe_print
            safe_print("异步会话预初始化完成")
        except Exception as e:
            from utils.async_logger import safe_print
            safe_print(f"异步会话预初始化失败: {e}")
