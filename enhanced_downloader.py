#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强型番茄小说下载器
集成参考代码的功能，支持GUI进度回调
"""

import time
import threading
import signal
import sys
import os
import json
import re
import random
import requests
import bs4
from ebooklib import epub
from fake_useragent import UserAgent
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, Dict

# 导入新的模块化组件
try:
    from config import CONFIG, Config
    from network import NetworkManager
    from content_processor import ContentProcessor
    from download_engine import DownloadEngine
    from file_output import FileOutputManager
    from state_manager import StateManager
except ImportError as e:
    print(f"模块导入失败: {e}")
    # 提供基本配置作为后备
    CONFIG = {
        "max_workers": 4,
        "request_timeout": 15,
        "status_file": "chapter.json",
        "auth_token": "wcnmd91jb",
        "server_url": "https://dlbkltos.s7123.xyz:5080/api/sources",
        "api_endpoints": [],
        "batch_config": {
            "enabled": False
        }
    }

# 全局锁
print_lock = threading.Lock()

class EnhancedNovelDownloader:
    """增强的小说下载器"""
    
    # 备用用户代理列表
    FALLBACK_USER_AGENTS = {
        'chrome': [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ],
        'edge': [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        ]
    }
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        """
        初始化增强型下载器
        
        Args:
            progress_callback: 进度回调函数 (progress, message)
        """
        self.progress_callback = progress_callback
        self.downloaded = set()
        self.chapter_results = {}
        self.lock = threading.Lock()
        self.is_cancelled = False
        
        # 初始化API端点
        self.fetch_api_endpoints_from_server()
    
    def log(self, message: str):
        """记录日志"""
        with print_lock:
            print(f"[{time.strftime('%H:%M:%S')}] {message}")
        if self.progress_callback:
            # 不改变进度，只更新消息
            self.progress_callback(-1, message)
    
    def update_progress(self, progress: float, message: str):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(progress, message)
    
    def make_request(self, url, headers=None, params=None, data=None, method='GET', verify=False, timeout=None):
        """通用的请求函数"""
        if headers is None:
            headers = self.get_headers()
        
        try:
            request_params = {
                'headers': headers,
                'params': params,
                'verify': verify,
                'timeout': timeout if timeout is not None else CONFIG["request_timeout"]
            }
            
            if data:
                request_params['json'] = data

            session = requests.Session()
            if method.upper() == 'GET':
                response = session.get(url, **request_params)
            elif method.upper() == 'POST':
                response = session.post(url, **request_params)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            return response
        except Exception as e:
            self.log(f"请求失败: {str(e)}")
            raise

    def get_headers(self) -> Dict[str, str]:
        """生成随机请求头"""
        browsers = ['chrome', 'edge']
        browser = random.choice(browsers)
        
        try:
            if browser == 'chrome':
                user_agent = UserAgent().chrome
            else:
                user_agent = UserAgent().edge
        except Exception as e:
            # fake_useragent 失败时使用备用用户代理
            print(f"fake_useragent获取用户代理失败，使用备用方案: {e}")
            user_agent = random.choice(self.FALLBACK_USER_AGENTS[browser])
        
        return {
            "User-Agent": user_agent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://fanqienovel.com/",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json"
        }

    def fetch_api_endpoints_from_server(self):
        """从服务器获取API列表"""
        try:
            headers = self.get_headers()
            headers["X-Auth-Token"] = CONFIG["auth_token"]
            
            response = requests.get(
                CONFIG["server_url"],
                headers=headers,
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                sources = data.get("sources", [])
                
                CONFIG["api_endpoints"] = []
                
                for source in sources:
                    if source["enabled"]:
                        endpoint = {"url": source["single_url"], "name": source["name"]}
                        CONFIG["api_endpoints"].append(endpoint)
                
                self.log("成功从服务器获取API列表!")
                return True
            else:
                self.log(f"获取API列表失败，状态码: {response.status_code}")
        except Exception as e:
            self.log(f"获取API列表异常: {str(e)}")

    def extract_chapters(self, soup):
        """解析章节列表"""
        chapters = []
        for idx, item in enumerate(soup.select('div.chapter-item')):
            a_tag = item.find('a')
            if not a_tag:
                continue
            
            raw_title = a_tag.get_text(strip=True)
            
            if re.match(r'^(番外|特别篇|if线)\s*', raw_title):
                final_title = raw_title
            else:
                clean_title = re.sub(
                    r'^第[一二三四五六七八九十百千\d]+章\s*',
                    '', 
                    raw_title
                ).strip()
                final_title = f"第{idx+1}章 {clean_title}"
            
            chapters.append({
                "id": a_tag['href'].split('/')[-1],
                "title": final_title,
                "url": f"https://fanqienovel.com{a_tag['href']}",
                "index": idx
            })
        return chapters


    def process_chapter_content(self, content):
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
            self.log(f"内容处理错误: {str(e)}")
            return str(content)

    def down_text(self, chapter_id, headers, book_id=None):
        """下载章节内容"""
        for idx, endpoint in enumerate(CONFIG["api_endpoints"]):
            if self.is_cancelled:
                return None, None
                
            current_endpoint = endpoint["url"]
            api_name = endpoint["name"]
            
            try:
                time.sleep(random.uniform(0.1, 0.5))
                
                if api_name == "fqweb":
                    url = f"http://fqweb.jsj66.com/content?item_id={chapter_id}"
                    
                    response = self.make_request(
                        url,
                        headers=headers.copy(),
                        timeout=CONFIG["request_timeout"],
                        verify=False
                    )
                    
                    if response and response.status_code == 200:
                        try:
                            data = response.json()
                            if data.get("data", {}).get("code") in ["0", 0]:
                                content = data.get("data", {}).get("data", {}).get("content", "")
                                if content:
                                    processed = self.process_chapter_content(content)
                                    return "", processed
                        except:
                            continue

            except Exception as e:
                if idx < len(CONFIG["api_endpoints"]) - 1:
                    with print_lock:
                        print(f"API {api_name} 请求异常: {str(e)[:50]}...，尝试切换")
                time.sleep(1)
            
            if idx < len(CONFIG["api_endpoints"]) - 1:
                self.log("正在切换到下一个api")
        
        with print_lock:
            print(f"章节 {chapter_id} 所有API均失败")
        return None, None

    def get_chapters_from_api(self, book_id, headers):
        """从API获取章节列表"""
        try:
            page_url = f'https://fanqienovel.com/page/{book_id}'
            response = requests.get(page_url, headers=headers, timeout=CONFIG["request_timeout"])
            soup = bs4.BeautifulSoup(response.text, 'html.parser')
            chapters = self.extract_chapters(soup)  
            
            api_url = f"https://fanqienovel.com/api/reader/directory/detail?bookId={book_id}"
            api_response = requests.get(api_url, headers=headers, timeout=CONFIG["request_timeout"])
            api_data = api_response.json()
            chapter_ids = api_data.get("data", {}).get("allItemIds", [])
            
            final_chapters = []
            for idx, chapter_id in enumerate(chapter_ids):
                web_chapter = next((ch for ch in chapters if ch["id"] == chapter_id), None)
                
                if web_chapter:
                    final_chapters.append({
                        "id": chapter_id,
                        "title": web_chapter["title"],
                        "index": idx
                    })
                else:
                    final_chapters.append({
                        "id": chapter_id,
                        "title": f"第{idx+1}章",
                        "index": idx
                    })
            
            return final_chapters
        except Exception as e:
            self.log(f"获取章节列表失败: {str(e)}")
            return None

    def create_epub_book(self, name, author_name, description, chapter_results, chapters):
        """创建EPUB文件"""
        book = epub.EpubBook()
        book.set_identifier(f'book_{name}_{int(time.time())}')
        book.set_title(name)
        book.set_language('zh-CN')
        book.add_author(author_name)
        book.add_metadata('DC', 'description', description)
        
        book.toc = []
        spine = ['nav']
        
        for idx in range(len(chapters)):
            if idx in chapter_results:
                result = chapter_results[idx]
                title = f'{result["base_title"]} {result["api_title"]}' if result["api_title"] else result["base_title"]
                chapter = epub.EpubHtml(
                    title=title,
                    file_name=f'chap_{idx}.xhtml',
                    lang='zh-CN'
                )
                content = result['content'].replace('\n', '<br/>')
                chapter.content = f'<h1>{title}</h1><p>{content}</p>'.encode('utf-8')
                book.add_item(chapter)
                book.toc.append(chapter)
                spine.append(chapter)
        
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine
        
        return book

    def download_chapter(self, chapter, headers, save_path, book_name, downloaded, book_id, file_format='txt'):
        """下载单个章节"""
        if chapter["id"] in downloaded:
            return None
        
        title, content = self.down_text(chapter["id"], headers, book_id)
        
        if content:
            if file_format == 'txt':
                output_file_path = os.path.join(save_path, f"{book_name}.txt")
                try:
                    with open(output_file_path, 'a', encoding='utf-8') as f:
                        f.write(f'{chapter["title"]}\n')
                        f.write(content + '\n\n')
                    
                    downloaded.add(chapter["id"])
                    self.save_status(save_path, downloaded)
                    return chapter["index"], content
                except Exception as e:
                    self.log(f"写入文件失败: {str(e)}")
            return chapter["index"], content
        return None

    def get_book_info(self, book_id, headers):
        """获取书名、作者、简介"""
        url = f'https://fanqienovel.com/page/{book_id}'
        try:
            response = requests.get(url, headers=headers, timeout=CONFIG["request_timeout"])
            if response.status_code != 200:
                self.log(f"网络请求失败，状态码: {response.status_code}")
                return None, None, None

            soup = bs4.BeautifulSoup(response.text, 'html.parser')
            
            name_element = soup.find('h1')
            name = name_element.text if name_element else "未知书名"
            
            author_name = "未知作者"
            author_name_element = soup.find('div', class_='author-name')
            if author_name_element:
                author_name_span = author_name_element.find('span', class_='author-name-text')
                if author_name_span:
                    author_name = author_name_span.text
            
            description = "无简介"
            description_element = soup.find('div', class_='page-abstract-content')
            if description_element:
                description_p = description_element.find('p')
                if description_p:
                    description = description_p.text
            
            return name, author_name, description
        except Exception as e:
            self.log(f"获取书籍信息失败: {str(e)}")
            return None, None, None

    def get_book_info_enhanced(self, book_id, headers):
        """
        使用fqweb API获取详细书籍信息
        返回比网页爬取更丰富的信息
        """
        try:
            url = f"http://fqweb.jsj66.com/info?book_id={book_id}"
            response = requests.get(url, headers=headers, timeout=CONFIG["request_timeout"])
            
            if response.status_code != 200:
                self.log(f"API请求失败，状态码: {response.status_code}")
                return None
            
            data = response.json()
            
            # 检查响应格式
            if not data.get('isSuccess') or data.get('data', {}).get('code') != '0':
                self.log("API返回错误信息")
                return None
            
            book_data = data['data']['data']
            
            # 构造增强的书籍信息
            enhanced_info = {
                'book_id': book_data.get('book_id', book_id),
                'book_name': book_data.get('book_name', '未知书名'),
                'author': book_data.get('author', '未知作者'),
                'author_id': book_data.get('author_id', ''),
                'abstract': book_data.get('abstract', '无简介'),
                'category': book_data.get('category', '未知分类'),
                'tags': book_data.get('tags', ''),
                'score': book_data.get('score', '0'),
                'word_number': book_data.get('word_number', '0'),
                'serial_count': book_data.get('serial_count', '0'),
                'creation_status': book_data.get('creation_status', '0'),  # 0=完结, 1=连载
                'read_count': book_data.get('read_count', '0'),
                'thumb_url': book_data.get('thumb_url', ''),
                'source': '番茄小说',
                'first_chapter_title': book_data.get('first_chapter_title', ''),
                'last_chapter_title': book_data.get('last_chapter_title', ''),
                'last_chapter_update_time': book_data.get('last_chapter_update_time', ''),
                'create_time': book_data.get('create_time', ''),
                'copyright_info': book_data.get('copyright_info', ''),
                'role': book_data.get('role', ''),  # 主角名
                
                # 作者信息
                'author_info': book_data.get('author_info', {}),
                
                # 标签详细信息
                'title_page_tags': book_data.get('title_page_tags', []),
                
                # 其他详细信息
                'genre': book_data.get('genre', '0'),
                'gender': book_data.get('gender', '1'),
                'exclusive': book_data.get('exclusive', '0'),
                'for_young': book_data.get('for_young', False),
                'platform': book_data.get('platform', '2'),
            }
            
            return enhanced_info
            
        except Exception as e:
            self.log(f"获取增强书籍信息失败: {str(e)}")
            return None

    def load_status(self, save_path):
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

    def save_status(self, save_path, downloaded):
        """保存下载状态"""
        status_file = os.path.join(save_path, CONFIG["status_file"])
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(list(downloaded), f, ensure_ascii=False, indent=2)

    def cancel_download(self):
        """取消下载"""
        self.is_cancelled = True
        self.log("用户取消下载")

    def run_download(self, book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, gui_callback=None):
        """
        运行下载
        
        Args:
            book_id: 书籍ID
            save_path: 保存路径
            file_format: 文件格式 ('txt' 或 'epub')
            start_chapter: 起始章节（可选，从0开始）
            end_chapter: 结束章节（可选，包含）
            gui_callback: 可选的GUI验证回调（占位以兼容调用方）
        """
        
        def signal_handler(sig, frame):
            self.log("检测到程序中断，正在保存已下载内容...")
            if hasattr(self, 'chapter_results') and self.chapter_results:
                try:
                    if 'output_file_path' in locals() and output_file_path:
                        self.write_downloaded_chapters_in_order(output_file_path, name, author_name, description, file_format)
                    if 'save_path' in locals() and hasattr(self, 'downloaded'):
                        self.save_status(save_path, self.downloaded)
                    self.log(f"已保存 {len(self.downloaded)} 个章节的进度")
                except:
                    pass
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        self.is_cancelled = False
        # 兼容GUI传入的验证回调（当前不在此类中直接使用，仅存储以备将来扩展）
        try:
            self.gui_verification_callback = gui_callback
        except Exception:
            # 保守处理，避免因属性设置导致异常
            pass
        self.downloaded = set()
        self.chapter_results = {}
        # 预定义变量，避免异常分支未定义引用
        name = None
        author_name = None
        description = None
        enhanced_info = None
        output_file_path = None
        
        try:
            self.update_progress(0, "开始下载...")
            
            headers = self.get_headers()
            chapters = self.get_chapters_from_api(book_id, headers)
            if not chapters:
                raise Exception("未找到任何章节，请检查小说ID是否正确。")
            
            self.update_progress(10, "获取书籍信息...")
            
            # 优先尝试使用增强API获取详细信息
            enhanced_info = self.get_book_info_enhanced(book_id, headers)
            if enhanced_info:
                name = enhanced_info['book_name']
                author_name = enhanced_info['author']
                description = enhanced_info['abstract']
                self.log("使用增强API获取到详细书籍信息")
            else:
                # 回退到原方法
                self.log("增强API失败，使用网页爬取方式")
                name, author_name, description = self.get_book_info(book_id, headers)
                enhanced_info = None
            
            if not name:
                name = f"未知小说_{book_id}"
                author_name = "未知作者"
                description = "无简介"

            # 处理章节范围
            if start_chapter is not None and end_chapter is not None:
                chapters = chapters[start_chapter:end_chapter+1]
                self.log(f"选择下载章节 {start_chapter+1}-{end_chapter+1}")

            self.downloaded = self.load_status(save_path)
            todo_chapters = [ch for ch in chapters if ch["id"] not in self.downloaded]
            
            if not todo_chapters:
                self.update_progress(100, "所有章节已是最新，无需下载")
                return

            self.update_progress(20, f"开始下载：《{name}》, 总章节数: {len(chapters)}, 待下载: {len(todo_chapters)}")
            os.makedirs(save_path, exist_ok=True)
            
            # 本地合法化文件名，避免Windows非法字符
            def _sanitize_filename(s: str) -> str:
                try:
                    import re
                    s = re.sub(r'[\\/:*?"<>|]', '_', s)
                    s = s.strip().rstrip('.')
                    return s or f"未知小说_{book_id}"
                except Exception:
                    return s

            safe_name = _sanitize_filename(name)
            output_file_path = os.path.join(save_path, f"{safe_name}.{file_format}")
            if file_format == 'txt' and not os.path.exists(output_file_path):
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(f"小说名: {name}\n作者: {author_name}\n内容简介: {description}\n\n")

            success_count = 0
            failed_chapters = []
            lock = threading.Lock()

            # 单章下载模式
            if todo_chapters:
                self.update_progress(70, f"开始单章下载模式，剩余 {len(todo_chapters)} 个章节...")
                
                def download_task(chapter):
                    nonlocal success_count
                    if self.is_cancelled:
                        return
                        
                    try:
                        title, content = self.down_text(chapter["id"], headers, book_id)
                        if content:
                            with lock:
                                self.chapter_results[chapter["index"]] = {
                                    "base_title": chapter["title"],
                                    "api_title": title,
                                    "content": content
                                }
                                self.downloaded.add(chapter["id"])
                                success_count += 1
                        else:
                            with lock:
                                failed_chapters.append(chapter)
                    except Exception as e:
                        self.log(f"章节 {chapter['id']} 下载失败！")
                        with lock:
                            failed_chapters.append(chapter)

                attempt = 1
                while todo_chapters and not self.is_cancelled:
                    self.log(f"第 {attempt} 次尝试，剩余 {len(todo_chapters)} 个章节...")
                    attempt += 1
                    
                    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
                        futures = [executor.submit(download_task, ch) for ch in todo_chapters]
                        
                        completed = 0
                        for future in as_completed(futures):
                            if self.is_cancelled:
                                break
                            completed += 1
                            progress = 70 + (completed / len(todo_chapters)) * 25  # 70%-95%
                            self.update_progress(progress, f"单章下载进度: {completed}/{len(todo_chapters)}")
                    
                    self.write_downloaded_chapters_in_order(output_file_path, name, author_name, description, file_format, enhanced_info)
                    self.save_status(save_path, self.downloaded)
                    todo_chapters = failed_chapters.copy()
                    failed_chapters = []
            return
            
        if file_format == 'txt':
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(f"小说名: {name}\n作者: {author_name}\n内容简介: {description}\n\n")
                for idx in sorted(self.chapter_results.keys()):
                    result = self.chapter_results[idx]
                    title = f'{result["base_title"]} {result["api_title"]}' if result["api_title"] else result["base_title"]
                    f.write(f"{title}\n{result['content']}\n\n")
        elif file_format == 'epub':
            # 传递增强信息到EPUB创建方法
            self._create_epub_with_enhanced_info(output_file_path, name, author_name, description, enhanced_info)

    def _create_epub_with_enhanced_info(self, output_file_path, name, author_name, description, enhanced_info):
        """使用增强信息创建EPUB文件"""
        book = epub.EpubBook()
        book.set_identifier(f'book_{name}_{int(time.time())}')
        book.set_title(name)
        book.set_language('zh-CN')
        book.add_author(author_name)
        book.add_metadata('DC', 'description', description)

        # 如果有增强信息，添加更多元数据
        if enhanced_info:
            if enhanced_info.get('category'):
                book.add_metadata('DC', 'subject', enhanced_info['category'])
            if enhanced_info.get('tags'):
                book.add_metadata('DC', 'subject', enhanced_info['tags'])

        # 创建CSS样式
        style = '''
        body { font-family: "Microsoft YaHei", "SimSun", serif; line-height: 1.8; margin: 20px; }
        h1 { text-align: center; color: #333; border-bottom: 2px solid #ccc; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .book-info { background-color: #f9f9f9; padding: 15px; border-left: 4px solid #4CAF50; margin: 20px 0; }
        .chapter { margin-top: 30px; }
        .chapter-title { font-size: 1.2em; font-weight: bold; color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; }
        .info-row { margin: 8px 0; }
        .info-label { font-weight: bold; color: #2c3e50; }
        '''
        
        nav_css = epub.EpubItem(uid="nav", file_name="style/nav.css", media_type="text/css", content=style)
        book.add_item(nav_css)

        # 创建详细信息页面
        info_html = self._generate_enhanced_book_info_html(name, author_name, description, enhanced_info)
        
        info_chapter = epub.EpubHtml(title='书籍信息', file_name='info.xhtml', lang='zh-CN')
        info_chapter.content = info_html
        book.add_item(info_chapter)

        book.toc = [info_chapter]
        spine = ['nav', info_chapter]

        # 添加封面（如果有）
        if enhanced_info and enhanced_info.get('thumb_url'):
            try:
                response = requests.get(enhanced_info['thumb_url'], timeout=10)
                if response.status_code == 200:
                    ext = 'jpg'
                    ct = response.headers.get('content-type', '')
                    if 'png' in ct:
                        ext = 'png'
                    elif 'webp' in ct:
                        ext = 'webp'
                    elif 'heic' in ct:
                        # EPUB不支持heic格式，转换为jpg
                        ext = 'jpg'
                        self.log("检测到HEIC格式封面，转换为JPG格式")
                    book.set_cover(f"cover.{ext}", response.content)
                    self.log(f"成功添加封面 (格式: {ext})")
            except Exception as e:
                self.log(f"封面下载失败: {e}")

        # 添加章节
        for idx in sorted(self.chapter_results.keys()):
            result = self.chapter_results[idx]
            title = f'{result["base_title"]} {result["api_title"]}' if result["api_title"] else result["base_title"]
            
            chapter = epub.EpubHtml(
                title=title,
                file_name=f'chap_{idx}.xhtml',
                lang='zh-CN'
            )
            
            # 将换行转换为HTML段落
            paragraphs = result['content'].split('\n')
            html_content = ""
            for para in paragraphs:
                para = para.strip()
                if para:
                    html_content += f"<p>{para}</p>\n"
            
            chapter_content = f"""
            <html>
            <head>
                <title>{title}</title>
                <link rel="stylesheet" type="text/css" href="style/nav.css"/>
            </head>
            <body>
                <div class="chapter">
                    <h2 class="chapter-title">{title}</h2>
                    {html_content}
                </div>
            </body>
            </html>
            """
            
            chapter.content = chapter_content
            book.add_item(chapter)
            book.toc.append(chapter)
            spine.append(chapter)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine
        
        epub.write_epub(output_file_path, book, {})

    def _generate_enhanced_book_info_html(self, name, author_name, description, enhanced_info):
        """生成增强的书籍信息HTML"""
        html_content = f"""
        <html>
        <head>
            <title>书籍信息</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>书籍信息</h1>
            <div class="book-info">
                <div class="info-row"><span class="info-label">书名：</span>{name}</div>
                <div class="info-row"><span class="info-label">作者：</span>{author_name}</div>
        """
        
        if enhanced_info:
            # 连载状态
            status_text = "完结" if enhanced_info.get('creation_status') == '0' else "连载中"
            html_content += f'<div class="info-row"><span class="info-label">状态：</span>{status_text}</div>'
            
            # 分类
            if enhanced_info.get('category'):
                html_content += f'<div class="info-row"><span class="info-label">分类：</span>{enhanced_info["category"]}</div>'
            
            # 字数
            if enhanced_info.get('word_number'):
                try:
                    word_count = int(enhanced_info['word_number'])
                    if word_count > 10000:
                        word_display = f"{word_count // 10000}万字"
                    else:
                        word_display = f"{word_count}字"
                    html_content += f'<div class="info-row"><span class="info-label">字数：</span>{word_display}</div>'
                except (ValueError, TypeError):
                    pass
            
            # 章节数
            if enhanced_info.get('serial_count'):
                html_content += f'<div class="info-row"><span class="info-label">章节数：</span>{enhanced_info["serial_count"]}章</div>'
            
            # 评分
            if enhanced_info.get('score') and enhanced_info['score'] != '0':
                try:
                    score_display = f"{float(enhanced_info['score']):.1f}分"
                    html_content += f'<div class="info-row"><span class="info-label">评分：</span>{score_display}</div>'
                except (ValueError, TypeError):
                    pass
            
            # 阅读量
            if enhanced_info.get('read_count'):
                try:
                    read_count = int(enhanced_info['read_count'])
                    if read_count > 10000:
                        read_display = f"{read_count // 10000}万次"
                    else:
                        read_display = f"{read_count}次"
                    html_content += f'<div class="info-row"><span class="info-label">阅读量：</span>{read_display}</div>'
                except (ValueError, TypeError):
                    pass
            
            # 标签
            if enhanced_info.get('tags'):
                html_content += f'<div class="info-row"><span class="info-label">标签：</span>{enhanced_info["tags"]}</div>'
            
            # 主角
            if enhanced_info.get('role'):
                html_content += f'<div class="info-row"><span class="info-label">主角：</span>{enhanced_info["role"]}</div>'
            
            # 首章和最新章节
            if enhanced_info.get('first_chapter_title'):
                html_content += f'<div class="info-row"><span class="info-label">首章：</span>{enhanced_info["first_chapter_title"]}</div>'
            
            if enhanced_info.get('last_chapter_title'):
                html_content += f'<div class="info-row"><span class="info-label">最新章节：</span>{enhanced_info["last_chapter_title"]}</div>'
            
            # 创建时间
            if enhanced_info.get('create_time'):
                html_content += f'<div class="info-row"><span class="info-label">创建时间：</span>{enhanced_info["create_time"]}</div>'
        
        html_content += f'<div class="info-row"><span class="info-label">来源：</span>番茄小说</div>'
        
        # 简介
        if description:
            desc_paragraphs = description.split('\n')
            desc_html = ""
            for para in desc_paragraphs:
                para = para.strip()
                if para:
                    desc_html += f"<p>{para}</p>"
            html_content += f'<div style="margin-top: 15px;"><span class="info-label">简介：</span><br/>{desc_html}</div>'
        
        # 版权信息
        if enhanced_info and enhanced_info.get('copyright_info'):
            html_content += f'<div style="margin-top: 15px; font-size: 0.9em; color: #666;"><span class="info-label">版权信息：</span><br/>{enhanced_info["copyright_info"]}</div>'
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        return html_content


# 为了兼容现有GUI，保持TomatoNovelAPI类的接口
class TomatoNovelAPI:
    def __init__(self):
        self.downloader = EnhancedNovelDownloader()
    
    def search_novels(self, keyword, offset=0, tab_type=1):
        """搜索小说 - 保持原有接口"""
        # 这里可以集成更多搜索功能，暂时返回示例
        return {
            "success": True,
            "data": {
                "items": [],
                "has_more": False,
                "next_offset": 0
            }
        }
    
    def get_novel_info(self, book_id):
        """获取小说信息 - 保持原有接口"""
        headers = self.downloader.get_headers()
        name, author, description = self.downloader.get_book_info(book_id, headers)
        
        if name:
            return {
                'isSuccess': True,
                'data': {
                    'data': {
                        'book_name': name,
                        'author': author,
                        'abstract': description,
                        'book_id': book_id
                    }
                }
            }
        return {'isSuccess': False, 'errorMsg': '获取书籍信息失败'}
    
    def get_book_details(self, book_id):
        """获取书籍详细信息（章节列表）"""
        headers = self.downloader.get_headers()
        chapters = self.downloader.get_chapters_from_api(book_id, headers)
        
        if chapters:
            all_item_ids = [ch["id"] for ch in chapters]
            return {
                "data": {
                    "allItemIds": all_item_ids
                },
                "isSuccess": True
            }
        return None
    
    def download_full_novel(self, book_id, item_ids, progress_callback=None):
        """下载整本小说"""
        if progress_callback:
            self.downloader.progress_callback = progress_callback
        
        # 这里需要根据item_ids确定章节范围
        # 暂时简化处理
        try:
            save_path = os.getcwd()  # 临时保存路径
            self.downloader.run_download(book_id, save_path, 'txt')
            
            # 读取结果
            headers = self.downloader.get_headers()
            name, _, _ = self.downloader.get_book_info(book_id, headers)
            file_path = os.path.join(save_path, f"{name or book_id}.txt")
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 模拟章节结构
                chapters = []
                for idx, item_id in enumerate(item_ids if isinstance(item_ids, list) else item_ids.split(',')):
                    chapters.append({
                        'title': f'第{idx+1}章',
                        'content': content  # 简化处理
                    })
                
                return {
                    'isSuccess': True,
                    'data': {
                        'data': chapters
                    }
                }
            
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"下载失败: {str(e)}")
        
        return {'isSuccess': False, 'errorMsg': '下载失败'}


if __name__ == "__main__":
    # 测试代码
    downloader = EnhancedNovelDownloader()
    
    def progress_callback(progress, message):
        print(f"Progress: {progress}% - {message}")
    
    downloader.progress_callback = progress_callback
    
    # 示例用法
    # downloader.run_download("7143038691944959011", "./downloads", "txt") 

def main():
    """主函数，提供完整的命令行交互界面"""
    print("""欢迎使用番茄小说下载器增强版！
基于参考代码修复，支持GUI进度回调
------------------------------------------""")
    
    # 初始化下载器
    downloader = EnhancedNovelDownloader()
    
    def progress_callback(progress, message):
        if progress >= 0:
            print(f"\r进度: {progress:.1f}% - {message}", end="", flush=True)
        else:
            print(f"\n{message}")
    
    downloader.progress_callback = progress_callback
    
    print("正在从服务器获取API列表...")
    downloader.fetch_api_endpoints_from_server()
    
    while True:
        book_id = input("\n请输入小说ID（输入q退出）：").strip()
        if book_id.lower() == 'q':
            break
            
        save_path = input("保存路径（留空为当前目录）：").strip() or os.getcwd()
        
        file_format = input("请选择下载格式（1: txt, 2: epub）：").strip()
        if file_format == '1':
            file_format = 'txt'
        elif file_format == '2':
            file_format = 'epub'
        else:
            print("无效的格式选择，将默认使用txt格式")
            file_format = 'txt'
        
        # 询问是否指定章节范围
        chapter_range = input("是否指定章节范围？(y/n，默认下载全部)：").strip().lower()
        start_chapter = None
        end_chapter = None
        
        if chapter_range == 'y':
            try:
                start_input = input("起始章节（从1开始）：").strip()
                end_input = input("结束章节（包含）：").strip()
                if start_input and end_input:
                    start_chapter = int(start_input) - 1  # 转换为0基索引
                    end_chapter = int(end_input) - 1
            except ValueError:
                print("章节范围输入错误，将下载全部章节")
        
        try:
            print(f"\n开始下载，格式：{file_format}")
            if start_chapter is not None and end_chapter is not None:
                print(f"章节范围：{start_chapter+1}-{end_chapter+1}")
            
            downloader.run_download(book_id, save_path, file_format, start_chapter, end_chapter)
            print("\n下载完成！")
            
        except Exception as e:
            print(f"\n运行错误: {str(e)}")
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main() 