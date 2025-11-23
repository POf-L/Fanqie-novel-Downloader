# -*- coding: utf-8 -*-
"""
番茄小说下载器核心模块 - 对接官方API https://fq.shusan.cn/docs
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
from typing import Optional, Dict, List
from ebooklib import epub
from config import CONFIG, print_lock, get_headers
import aiohttp
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from watermark import apply_watermark_to_chapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

# ===================== 官方API管理器 =====================

class APIManager:
    """番茄小说官方API统一管理器 - https://fq.shusan.cn/docs
    支持同步和异步两种调用方式
    """
    
    def __init__(self):
        self.base_url = CONFIG["api_base_url"]
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
                print(f"搜索异常: {str(e)}")
            return None
    
    def get_book_detail(self, book_id: str) -> Optional[Dict]:
        """获取书籍详情"""
        try:
            url = f"{self.base_url}{self.endpoints['detail']}"
            params = {"book_id": book_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
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
                print(f"获取书籍详情异常: {str(e)}")
            return None
    
    def get_chapter_list(self, book_id: str) -> Optional[List[Dict]]:
        """获取章节列表"""
        try:
            url = f"{self.base_url}{self.endpoints['book']}"
            params = {"book_id": book_id}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=CONFIG["request_timeout"])
            
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
                print(f"获取章节列表异常: {str(e)}")
            return None
    
    def get_chapter_content(self, item_id: str) -> Optional[Dict]:
        """获取章节内容(同步)"""
        try:
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
                print(f"获取章节内容异常: {str(e)}")
            return None

    async def get_chapter_content_async(self, item_id: str) -> Optional[Dict]:
        """获取章节内容(异步)"""
        max_retries = CONFIG.get("max_retries", 3)
        
        async with self.semaphore:
            async with self.request_lock:
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                if time_since_last < CONFIG.get("download_delay", 0.5):
                    await asyncio.sleep(CONFIG.get("download_delay", 0.5) - time_since_last)
                self.last_request_time = time.time()
            
            session = await self._get_async_session()
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
        """获取整本小说内容(纯文本)"""
        try:
            url = f"{self.base_url}{self.endpoints['content']}"
            # 使用 tab='下载' 获取整书内容
            params = {"book_id": book_id, "tab": "下载"}
            response = self._get_session().get(url, params=params, headers=get_headers(), timeout=60, stream=True)
            
            if response.status_code == 200:
                # 手动解码，防止编码问题
                response.encoding = 'utf-8'
                return response.text
            return None
        except Exception as e:
            with print_lock:
                print(f"获取整书内容异常: {str(e)}")
            return None

def parse_novel_text(text: str) -> List[Dict]:
    """解析整本小说文本，分离章节"""
    lines = text.splitlines()
    chapters = []
    
    current_chapter = None
    current_content = []
    
    # 匹配章节标题 (支持 "第xxx章" 或 "数字. ")
    chapter_pattern = re.compile(r'^\s*(第[0-9一二三四五六七八九十百千]+章|[0-9]+\.)\s*.*')
    
    for line in lines:
        match = chapter_pattern.match(line)
        if match:
            # 保存上一章
            if current_chapter:
                current_chapter['content'] = '\n'.join(current_content)
                chapters.append(current_chapter)
            
            # 开始新章
            title = line.strip()
            current_chapter = {
                'title': title,
                'id': str(len(chapters)), # 生成虚拟ID
                'index': len(chapters)
            }
            current_content = []
        else:
            # 如果已经在章节中，添加到内容
            if current_chapter:
                current_content.append(line)
            # 否则忽略(头部元数据)
    
    # 保存最后一章
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


def load_status(save_path):
    """加载下载状态"""
    status_file = os.path.join(save_path, CONFIG.get("status_file", ".download_status.json"))
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except:
            pass
    return set()


def save_status(save_path, downloaded_ids):
    """保存下载状态"""
    status_file = os.path.join(save_path, CONFIG.get("status_file", ".download_status.json"))
    try:
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(list(downloaded_ids), f, ensure_ascii=False, indent=2)
    except Exception as e:
        with print_lock:
            print(f"保存下载状态失败: {str(e)}")


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
            print(f"下载封面失败: {str(e)}")
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
                print(f"添加封面失败: {str(e)}")
    
    spine_items = ['nav']
    toc_items = []
    
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
    
    filename = re.sub(r'[\\/:*?"<>|]', '_', name)
    epub_path = os.path.join(save_path, f'{filename}.epub')
    epub.write_epub(epub_path, book)
    
    return epub_path


def create_txt(name, author_name, description, chapters, save_path):
    """创建TXT文件"""
    filename = re.sub(r'[\\/:*?"<>|]', '_', name)
    txt_path = os.path.join(save_path, f'{filename}.txt')
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"{name}\n")
        if author_name:
            f.write(f"作者: {author_name}\n")
        if description:
            f.write(f"\n简介:\n{description}\n")
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
        log_message("正在获取书籍信息...", 5)
        book_detail = api.get_book_detail(book_id)
        if not book_detail:
            log_message("获取书籍信息失败")
            return False
        
        name = book_detail.get("book_name", f"未知小说_{book_id}")
        author_name = book_detail.get("author", "未知作者")
        description = book_detail.get("abstract", "")
        cover_url = book_detail.get("thumb_url", "")
        
        log_message(f"书名: {name}, 作者: {author_name}", 10)
        
        chapter_results = {}
        use_full_download = False
        
        # 尝试极速下载模式 (仅当没有指定范围且没有选择特定章节时)
        if start_chapter is None and end_chapter is None and not selected_chapters:
            log_message("正在尝试极速下载模式 (整书下载)...", 15)
            full_text = api.get_full_content(book_id)
            if full_text:
                log_message("整书内容获取成功，正在解析...", 30)
                chapters_parsed = parse_novel_text(full_text)
                
                if chapters_parsed:
                    log_message(f"解析成功，共 {len(chapters_parsed)} 章", 50)
                    # 处理章节内容
                    with tqdm(total=len(chapters_parsed), desc="处理章节", disable=gui_callback is not None) as pbar:
                        for i, ch in enumerate(chapters_parsed):
                            processed = process_chapter_content(ch['content'])
                            chapter_results[ch['index']] = {
                                'title': ch['title'],
                                'content': processed
                            }
                            if pbar: pbar.update(1)
                    
                    use_full_download = True
                    log_message("章节处理完成", 80)
                else:
                    log_message("解析失败或未找到章节，切换回普通模式")
            else:
                log_message("极速下载失败，切换回普通模式")

        # 如果没有使用极速模式，则走普通模式
        if not use_full_download:
            log_message("正在获取章节列表...", 15)
            chapters_data = api.get_chapter_list(book_id)
            if not chapters_data:
                log_message("获取章节列表失败")
                return False
            
            chapters = []
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
                log_message("未找到章节")
                return False
            
            total_chapters = len(chapters)
            log_message(f"共找到 {total_chapters} 章", 20)
            
            if start_chapter is not None or end_chapter is not None:
                start_idx = (start_chapter - 1) if start_chapter else 0
                end_idx = end_chapter if end_chapter else total_chapters
                chapters = chapters[start_idx:end_idx]
                log_message(f"下载章节范围: {start_idx+1} 到 {end_idx}")
            
            if selected_chapters:
                try:
                    selected_indices = set(int(x) for x in selected_chapters)
                    chapters = [ch for ch in chapters if ch['index'] in selected_indices]
                    log_message(f"已选择 {len(chapters)} 个特定章节")
                except Exception as e:
                    log_message(f"章节筛选出错: {e}")
            
            downloaded_ids = load_status(save_path)
            chapters_to_download = [ch for ch in chapters if ch["id"] not in downloaded_ids]
            
            if not chapters_to_download:
                log_message("所有章节已下载")
            else:
                log_message(f"开始下载 {len(chapters_to_download)} 章...", 25)
            
            completed = 0
            total_tasks = len(chapters_to_download)
            
            with tqdm(total=total_tasks, desc="下载进度", disable=gui_callback is not None) as pbar:
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
                                    gui_callback(progress, f"已下载: {completed}/{total_tasks}")
                        except Exception:
                            pass
            
            save_status(save_path, downloaded_ids)
        
        if gui_callback:
            gui_callback(85, "正在生成文件...")
        
        sorted_chapters = [chapter_results[idx] for idx in sorted(chapter_results.keys()) if idx in chapter_results]

        
        if file_format == 'epub':
            output_file = create_epub(name, author_name, description, cover_url, sorted_chapters, save_path)
        else:
            output_file = create_txt(name, author_name, description, sorted_chapters, save_path)
        
        log_message(f"下载完成! 文件: {output_file}", 100)
        return True
        
    except Exception as e:
        log_message(f"下载失败: {str(e)}")
        return False


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
                print(f"搜索失败: {str(e)}")
            return None


downloader_instance = NovelDownloader()

def signal_handler(sig, frame):
    """信号处理"""
    print('\n正在取消下载...')
    downloader_instance.cancel_download()
    sys.exit(0)


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGINT, signal_handler)
    except ValueError:
        pass
    
    print("番茄小说下载器")
    print("="*50)
    book_id = input("请输入书籍ID: ").strip()
    save_path = input("请输入保存路径(默认: ./novels): ").strip() or "./novels"
    file_format = input("选择格式 (txt/epub, 默认: txt): ").strip() or "txt"
    
    os.makedirs(save_path, exist_ok=True)
    
    success = Run(book_id, save_path, file_format)
    if success:
        print("下载完成!")
    else:
        print("下载失败!")
