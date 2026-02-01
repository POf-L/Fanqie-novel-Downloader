# -*- coding: utf-8 -*-
"""
API源管理器 - 处理API源探测和选择
"""

import os
import sys
import time
import socket
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加父目录到路径
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        _base_path = sys._MEIPASS
    else:
        _base_path = os.path.dirname(sys.executable)
    if _base_path not in sys.path:
        sys.path.insert(0, _base_path)
else:
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

from config.config import CONFIG, _LOCAL_CONFIG_FILE


def _get_ip_location(ip: str, timeout: float = 2.0) -> dict:
    """查询IP地理位置信息（英文）

    Args:
        ip: IP地址
        timeout: 超时时间（秒）

    Returns:
        包含位置信息的字典，格式: {'country': 'China', 'region': 'Sichuan', 'city': 'Chengdu', 'isp': 'Alibaba'}
    """
    try:
        url = f"http://ip-api.com/json/{ip}?lang=en&fields=status,country,regionName,city,isp"
        with requests.Session() as sess:
            sess.trust_env = False
            resp = sess.get(url, timeout=timeout)

        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                return {
                    'country': data.get('country', ''),
                    'region': data.get('regionName', ''),
                    'city': data.get('city', ''),
                    'isp': data.get('isp', '')
                }
    except Exception:
        pass

    return {}


def _format_location_name(location: dict) -> str:
    """格式化位置信息为节点名称

    Args:
        location: 位置信息字典

    Returns:
        格式化的名称，如 "中国|四川省|成都市|阿里云"
    """
    parts = []
    if location.get('country'):
        parts.append(location['country'])
    if location.get('region'):
        parts.append(location['region'])
    if location.get('city'):
        parts.append(location['city'])
    if location.get('isp'):
        parts.append(location['isp'])

    return '|'.join(parts) if parts else ''


def _normalize_base_url(url: str) -> str:
    return (url or '').strip().rstrip('/')


def _get_api_sources() -> list:
    """从配置获取可选 API 接口列表"""
    try:
        if CONFIG is None:
            return []
        sources = CONFIG.get('api_sources') or []
        normalized = []
        for s in sources:
            if isinstance(s, dict):
                base_url = _normalize_base_url(s.get('base_url') or s.get('api_base_url') or '')
                if base_url:
                    item = {
                        'name': s.get('name') or base_url,
                        'base_url': base_url
                    }
                    if 'supports_full_download' in s:
                        item['config_supports_full_download'] = bool(s['supports_full_download'])
                    normalized.append(item)
            elif isinstance(s, str):
                base_url = _normalize_base_url(s)
                if base_url:
                    normalized.append({'name': base_url, 'base_url': base_url})

        # 回退：至少包含当前 base_url
        base = _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))
        if base and not any(x['base_url'] == base for x in normalized):
            normalized.insert(0, {'name': base, 'base_url': base})

        # 去重
        seen = set()
        deduped = []
        for s in normalized:
            if s['base_url'] in seen:
                continue
            seen.add(s['base_url'])
            deduped.append(s)

        return deduped
    except Exception:
        return []


def _probe_api_source(base_url: str, timeout: float = 1.5, config_supports_full: bool = None) -> dict:
    """HTTP 探活（ping 域名根路径 + 检测全量下载支持）"""
    from urllib.parse import urlparse

    base_url = _normalize_base_url(base_url)
    parsed = urlparse(base_url)
    ping_url = f"{parsed.scheme}://{parsed.netloc}/"

    start = time.perf_counter()
    resolved_ip = None
    location = {}
    dynamic_name = None
    supports_full_download = False

    try:
        # 解析域名获取IP地址
        hostname = parsed.hostname
        if hostname:
            try:
                resolved_ip = socket.gethostbyname(hostname)
                # 查询IP地理位置（仅对可用节点查询，节省时间）
                location = _get_ip_location(resolved_ip, timeout=1.5)
                if location:
                    dynamic_name = _format_location_name(location)
            except Exception:
                pass

        sess = requests.Session()
        sess.trust_env = bool(CONFIG.get("use_system_proxy", False))
        search_endpoint = (CONFIG.get('endpoints') or {}).get('search', '/api/search')
        search_url = f"{base_url}{search_endpoint}"
        search_params = {"key": "test", "tab_type": "3", "offset": "0"}
        resp = sess.get(search_url, params=search_params, timeout=timeout, allow_redirects=True)
        latency_ms = int((time.perf_counter() - start) * 1000)

        # 只要能连上就认为可用
        available = False
        try:
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get('code') == 200:
                    available = True
        except Exception:
            available = False

        # 如果节点可用，判断是否支持全量下载
        if available:
            # 优先使用配置文件中的手动设置
            if config_supports_full is not None:
                supports_full_download = config_supports_full
            else:
                # 自动探测
                try:
                    test_url = f"{base_url}/api/content"
                    test_params = {"book_id": "0", "tab": "小说"}
                    test_resp = sess.get(test_url, params=test_params, timeout=min(2.0, timeout))
                    if test_resp.status_code == 200:
                        try:
                            data = test_resp.json()
                            if 'code' in data:
                                supports_full_download = True
                        except Exception:
                            pass
                except Exception:
                    supports_full_download = False

        result = {
            'available': available,
            'latency_ms': latency_ms,
            'status_code': resp.status_code,
            'error': None,
            'supports_full_download': supports_full_download
        }

        # 添加IP和位置信息
        if resolved_ip:
            result['resolved_ip'] = resolved_ip
        if location:
            result['location'] = location
        if dynamic_name:
            result['dynamic_name'] = dynamic_name

        try:
            _sess = locals().get("sess")
            if _sess:
                _sess.close()
        except Exception:
            pass

        return result

    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        result = {
            'available': False,
            'latency_ms': latency_ms,
            'status_code': None,
            'error': str(e),
            'supports_full_download': False
        }

        # 即使失败也尝试添加IP信息
        if resolved_ip:
            result['resolved_ip'] = resolved_ip
        if location:
            result['location'] = location
        if dynamic_name:
            result['dynamic_name'] = dynamic_name

        try:
            _sess = locals().get("sess")
            if _sess:
                _sess.close()
        except Exception:
            pass

        return result


def _apply_api_base_url(base_url: str) -> None:
    """应用 API base_url 到运行时（CONFIG + APIManager）"""
    if CONFIG is None:
        return

    base_url = _normalize_base_url(base_url)
    if not base_url:
        return

    CONFIG['api_base_url'] = base_url

    # 更新APIManager的base_url
    try:
        from core.api_manager import get_api_manager
        api_manager = get_api_manager()
        if api_manager:
            api_manager.base_url = base_url
            # 重置线程局部 Session，避免连接复用导致的问题
            if hasattr(api_manager, '_tls'):
                api_manager._tls = threading.local()
    except Exception:
        pass


def _read_local_config() -> dict:
    """读取本地配置"""
    try:
        if os.path.exists(_LOCAL_CONFIG_FILE):
            import json
            with open(_LOCAL_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _write_local_config(updates: dict) -> bool:
    """写入本地配置"""
    try:
        config_file = _LOCAL_CONFIG_FILE
        
        cfg = _read_local_config()
        cfg.update(updates or {})
        
        import json
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _ensure_api_base_url(force_mode=None) -> str:
    """
    确保 CONFIG.api_base_url 已设置；若为空/不可用则自动选择最快节点。

    Returns:
        str: 当前/选中的 base_url（可能为空）
    """
    if CONFIG is None:
        return ''

    sources = _get_api_sources()
    if not sources:
        return _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))

    local_cfg = _read_local_config()
    mode = str(local_cfg.get('api_base_url_mode', 'auto') or 'auto').lower()
    if force_mode:
        mode = str(force_mode).lower()

    current = _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))

    # 手动模式优先
    if mode == 'manual':
        manual_url = _normalize_base_url(str(local_cfg.get('api_base_url', '') or ''))
        if manual_url:
            probe = _probe_api_source(manual_url, timeout=1.5)
            if probe.get('available'):
                _apply_api_base_url(manual_url)
                return manual_url

    # 并发探测全部并选择延迟最低的可用项
    results = []
    with ThreadPoolExecutor(max_workers=min(10, len(sources))) as ex:
        fut_map = {ex.submit(_probe_api_source, s['base_url'], 1.5, s.get('config_supports_full_download')): s for s in sources}
        for fut in as_completed(fut_map):
            src = fut_map[fut]
            try:
                probe = fut.result()
            except Exception as e:
                probe = {'available': False, 'latency_ms': None, 'status_code': None, 'error': str(e)}
            results.append({**src, **probe})

    # 按优先级排序：1. 支持全量下载优先 2. 延迟最低
    available = [r for r in results if r.get('available')]
    available.sort(key=lambda x: (
        not x.get('supports_full_download', False),
        x.get('latency_ms') or 999999
    ))

    if available:
        best = available[0]['base_url']
        _apply_api_base_url(best)
        _write_local_config({'api_base_url_mode': 'auto', 'api_base_url': best})
        return best

    return current
