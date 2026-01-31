# -*- coding: utf-8 -*-
"""
更新下载器 - 处理应用更新下载
"""

import os
import sys
import time
import threading
import requests
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

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

from config.config import CONFIG


# 更新下载状态
update_download_status = {
    'is_downloading': False,
    'progress': 0,
    'message': '',
    'filename': '',
    'total_size': 0,
    'downloaded_size': 0,
    'completed': False,
    'error': None,
    'save_path': '',
    'temp_file_path': '',
    'thread_count': 1,
    'thread_progress': [],
    'merging': False
}
update_lock = threading.Lock()


def get_update_status():
    """获取更新下载状态"""
    with update_lock:
        return update_download_status.copy()


def set_update_status(**kwargs):
    """设置更新下载状态"""
    with update_lock:
        for key, value in kwargs.items():
            if key in update_download_status:
                update_download_status[key] = value


def test_url_connectivity(url, timeout=8):
    """测试 URL 连通性"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    test_url = f"{parsed.scheme}://{parsed.netloc}"
    
    print(f'[DEBUG] Testing connection to: {test_url}')
    try:
        resp = requests.head(test_url, timeout=timeout, allow_redirects=True)
        if resp.status_code < 500:
            print(f'[DEBUG] Connection OK (status: {resp.status_code})')
            return True
    except Exception as e:
        print(f'[DEBUG] Connection failed: {e}')
    
    return False


def download_chunk_adaptive(url, start, end, chunk_id, temp_file, progress_dict, total_size, cancel_flag):
    """下载文件的一个分块（极速版本）"""
    headers = {'Range': f'bytes={start}-{end}'}
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=60, allow_redirects=True)
        response.raise_for_status()

        chunk_size = 131072  # 128KB chunks
        downloaded = 0
        chunk_total = end - start + 1
        last_time = time.time()
        last_downloaded = 0

        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if cancel_flag.get('cancelled'):
                    return {'success': False, 'reason': 'cancelled'}
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # 减少进度更新频率
                    now = time.time()
                    if now - last_time >= 0.2:
                        speed = (downloaded - last_downloaded) / (now - last_time)
                        last_time = now
                        last_downloaded = downloaded
                        progress_dict[chunk_id] = {
                            'downloaded': downloaded,
                            'total': chunk_total,
                            'percent': int((downloaded / chunk_total) * 100) if chunk_total > 0 else 0,
                            'speed': speed
                        }

        progress_dict[chunk_id] = {
            'downloaded': chunk_total,
            'total': chunk_total,
            'percent': 100,
            'speed': 0
        }
        return {'success': True, 'chunk_id': chunk_id}
    except Exception as e:
        print(f'[DEBUG] Chunk {chunk_id} download error: {e}')
        return {'success': False, 'reason': str(e), 'chunk_id': chunk_id}


def update_download_worker(url, save_path, filename):
    """更新下载工作线程 - 优化版：减少初始化延迟"""
    print(f'[DEBUG] update_download_worker started (optimized for fast initialization)')
    print(f'[DEBUG]   url: {url}')
    print(f'[DEBUG]   save_path: {save_path}')
    print(f'[DEBUG]   filename: {filename}')

    # 优化配置
    INITIAL_THREADS = 8
    MAX_THREADS = 16
    MIN_CHUNK_SIZE = 1024 * 1024

    try:
        set_update_status(
            is_downloading=True,
            progress=0,
            message="正在连接服务器...",
            filename=filename,
            completed=False,
            error=None,
            save_path=save_path,
            thread_count=INITIAL_THREADS,
            thread_progress=[],
            merging=False
        )

        import tempfile

        # 优化：并行执行连通性测试和文件信息获取
        async def fast_init():
            import aiohttp

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=8, connect=2),
                connector=aiohttp.TCPConnector(limit=10)
            ) as session:
                try:
                    async with session.head(url, allow_redirects=True) as response:
                        if response.status == 200:
                            total_size = int(response.headers.get('content-length', 0))
                            supports_range = response.headers.get('accept-ranges', '').lower() == 'bytes'
                            final_url = str(response.url)
                            return {
                                'success': True,
                                'total_size': total_size,
                                'supports_range': supports_range,
                                'final_url': final_url
                            }
                        else:
                            return {'success': False, 'error': f'HTTP {response.status}'}
                except asyncio.TimeoutError:
                    return {'success': False, 'error': '连接超时'}
                except Exception as e:
                    return {'success': False, 'error': str(e)}

        # 运行异步初始化
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            init_result = loop.run_until_complete(fast_init())
            loop.close()
        except Exception as e:
            print(f'[DEBUG] Async init failed, falling back to sync: {e}')
            try:
                response = requests.head(url, timeout=(2, 5), allow_redirects=True)
                if response.status_code == 200:
                    init_result = {
                        'success': True,
                        'total_size': int(response.headers.get('content-length', 0)),
                        'supports_range': response.headers.get('accept-ranges', '').lower() == 'bytes',
                        'final_url': response.url
                    }
                else:
                    init_result = {'success': False, 'error': f'HTTP {response.status}'}
            except Exception as e2:
                init_result = {'success': False, 'error': str(e2)}

        if not init_result['success']:
            raise Exception(f"连接失败: {init_result['error']}")

        total_size = init_result['total_size']
        supports_range = init_result['supports_range']
        final_url = init_result['final_url']

        print(f'[DEBUG] Fast init completed - Size: {total_size}, Range: {supports_range}')

        # 使用程序运行目录的 cache 文件夹
        cache_dir = os.path.join(get_config_dir(), '..', 'cache')
        os.makedirs(cache_dir, exist_ok=True)

        temp_filename = filename + '.new'
        full_path = os.path.join(cache_dir, temp_filename)

        # 智能选择下载策略
        use_multithread = (
            total_size > 5 * 1024 * 1024 and  # 文件大于5MB
            supports_range and
            get_update_status()['is_downloading']
        )

        if not use_multithread:
            print(f'[DEBUG] Using optimized single-thread download')
            set_update_status(thread_count=1, total_size=total_size, message="开始下载...")

            response = requests.get(final_url, stream=True, timeout=(3, 60), allow_redirects=True)
            response.raise_for_status()

            if total_size == 0:
                total_size = int(response.headers.get('content-length', 0))

            downloaded = 0
            last_update = time.time()
            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=131072):
                    if not get_update_status()['is_downloading']:
                        break
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if now - last_update >= 0.2:
                            progress = int((downloaded / total_size) * 100) if total_size > 0 else min(99, downloaded // 100000)
                            set_update_status(
                                progress=progress,
                                downloaded_size=downloaded,
                                total_size=total_size,
                                thread_progress=[{'downloaded': downloaded, 'total': total_size or downloaded, 'percent': progress, 'speed': 0}],
                                message=f'下载中: {progress}%' if total_size > 0 else f'已下载 {downloaded // 1024} KB'
                            )
                            last_update = now
        else:
            # 优化的多线程下载
            print(f'[DEBUG] Using optimized multi-thread download')

            optimal_threads = min(MAX_THREADS, max(4, total_size // (2 * 1024 * 1024)))
            chunk_size = max(MIN_CHUNK_SIZE, total_size // optimal_threads)

            print(f'[DEBUG] Optimized config - Threads: {optimal_threads}, Chunk size: {chunk_size}')
            set_update_status(total_size=total_size, thread_count=optimal_threads, message="准备多线程下载...")

            cancel_flag = {'cancelled': False}
            progress_dict = {}
            chunks = []

            start = 0
            chunk_id = 0
            while start < total_size:
                end = min(start + chunk_size - 1, total_size - 1)
                temp_file = os.path.join(cache_dir, f'{filename}.part{chunk_id}')
                chunks.append((chunk_id, start, end, temp_file))
                start = end + 1
                chunk_id += 1

            print(f'[DEBUG] Created {len(chunks)} optimized chunks')

            completed_chunks = []
            failed_chunks = []

            def update_progress():
                """优化的进度更新"""
                total_downloaded = sum(p.get('downloaded', 0) for p in progress_dict.values())
                overall_progress = int((total_downloaded / total_size) * 100) if total_size > 0 else 0
                overall_progress = min(99, overall_progress)

                thread_progress = [
                    {'downloaded': p.get('downloaded', 0), 'total': p.get('total', 0), 'percent': p.get('percent', 0), 'speed': p.get('speed', 0)}
                    for p in progress_dict.values()
                ]

                set_update_status(
                    progress=overall_progress,
                    downloaded_size=total_downloaded,
                    thread_count=len([p for p in progress_dict.values() if p.get('percent', 0) < 100]),
                    thread_progress=thread_progress,
                    message=f'多线程下载: {overall_progress}%'
                )
                return total_downloaded

            # 使用优化的线程池
            with ThreadPoolExecutor(max_workers=optimal_threads, thread_name_prefix="UpdateDL") as executor:
                future_to_chunk = {}
                for chunk_info in chunks:
                    chunk_id, start, end, temp_file = chunk_info
                    future = executor.submit(
                        download_chunk_adaptive, final_url, start, end,
                        chunk_id, temp_file, progress_dict, total_size, cancel_flag
                    )
                    future_to_chunk[future] = chunk_info

                last_progress_update = time.time()
                while future_to_chunk:
                    if not get_update_status()['is_downloading']:
                        cancel_flag['cancelled'] = True
                        for future in future_to_chunk:
                            future.cancel()
                        break

                    done_futures = [f for f in future_to_chunk if f.done()]
                    for future in done_futures:
                        chunk_info = future_to_chunk.pop(future)
                        chunk_id, start, end, temp_file = chunk_info
                        try:
                            result = future.result()
                            if result.get('success'):
                                completed_chunks.append(chunk_info)
                            else:
                                print(f'[DEBUG] Chunk {chunk_id} failed: {result.get("reason")}')
                                failed_chunks.append(chunk_info)
                        except Exception as e:
                            print(f'[DEBUG] Chunk {chunk_id} exception: {e}')
                            failed_chunks.append(chunk_info)

                    now = time.time()
                    if now - last_progress_update >= 0.1:
                        update_progress()
                        last_progress_update = now

                    time.sleep(0.02)

                # 简化重试逻辑
                if failed_chunks and not cancel_flag['cancelled']:
                    print(f'[DEBUG] Retrying {len(failed_chunks)} failed chunks')
                    retry_futures = {}
                    for chunk_info in failed_chunks:
                        chunk_id, start, end, temp_file = chunk_info
                        future = executor.submit(
                            download_chunk_adaptive, final_url, start, end,
                            chunk_id, temp_file, progress_dict, total_size, cancel_flag
                        )
                        retry_futures[future] = chunk_info

                    for future in retry_futures:
                        chunk_info = retry_futures[future]
                        try:
                            result = future.result()
                            if result.get('success'):
                                completed_chunks.append(chunk_info)
                        except Exception:
                            pass

            # 检查下载完整性
            if len(completed_chunks) < len(chunks) * 0.8:
                raise Exception(f'下载不完整: {len(completed_chunks)}/{len(chunks)} 个分块成功')

            # 合并文件
            if completed_chunks and get_update_status()['is_downloading']:
                print(f'[DEBUG] Merging {len(completed_chunks)} chunks...')
                set_update_status(
                    progress=100,
                    message="正在合并文件...",
                    merging=True
                )

                completed_chunks.sort(key=lambda x: x[0])

                with open(full_path, 'wb') as output_file:
                    for chunk_id, start, end, temp_file in completed_chunks:
                        if os.path.exists(temp_file):
                            with open(temp_file, 'rb') as chunk_file:
                                output_file.write(chunk_file.read())
                            os.remove(temp_file)

                # 清理剩余临时文件
                for chunk_id, start, end, temp_file in chunks:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

        if get_update_status()['is_downloading']:
            print(f'[DEBUG] Download completed successfully!')
            print(f'[DEBUG] File saved to: {full_path}')
            if os.path.exists(full_path):
                file_size = os.path.getsize(full_path)
                print(f'[DEBUG] Final file size: {file_size} bytes')
                set_update_status(
                    progress=100,
                    message="下载完成！",
                    completed=True,
                    merging=False,
                    save_path=full_path
                )
            else:
                raise Exception('下载的文件不存在')
        else:
            print(f'[DEBUG] Download was cancelled')
            if os.path.exists(full_path):
                os.remove(full_path)
            set_update_status(
                is_downloading=False,
                progress=0,
                message="下载已取消",
                completed=False,
                error="用户取消"
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        print(f'[DEBUG] Download failed: {error_msg}')
        set_update_status(
            is_downloading=False,
            progress=0,
            message=f"下载失败: {error_msg}",
            completed=False,
            error=error_msg
        )


def get_config_dir():
    """获取配置文件目录"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    config_dir = os.path.join(base_dir, 'config')
    os.makedirs(config_dir, exist_ok=True)
    return config_dir
