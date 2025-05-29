import requests,random,json,os,time,re
from bs4 import BeautifulSoup
from config import CONFIG
from local_crawler import FanQieChapter


class CookieGenerationError(Exception):
    pass
class RequestHandler:
    def __init__(self):
        self.config=CONFIG["request"];self.session=requests.Session();self.use_local_crawler=self.config.get("use_local_crawler",False)

    def get_headers(self,c=None):
        return {"User-Agent":random.choice(self.config["user_agents"]),"Cookie":c or self.get_cookie()}

    def get_cookie(self):
        cookie_path = CONFIG["file"]["cookie_file"]
        last_error=None
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)
                    if isinstance(cookie_data, str):
                        return cookie_data
                    else:
                        last_error = f"Cookie 文件 '{cookie_path}' 格式不正确"
            except FileNotFoundError:
                pass
            except json.JSONDecodeError:
                last_error = f"Cookie 文件 '{cookie_path}' 解析失败"
            except Exception as e:
                last_error = f"读取 Cookie 文件时发生错误: {e}"
        
        for attempt in range(10):
            novel_web_id = random.randint(10**18, 10**19-1)
            cookie = f'novel_web_id={novel_web_id}'
            try:
                resp = self.session.get(
                    'https://fanqienovel.com',
                    headers={"User-Agent": random.choice(self.config["user_agents"])},
                    cookies={"novel_web_id": str(novel_web_id)},
                    timeout=10
                )
                if resp.ok:
                    os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
                    with open(cookie_path, 'w', encoding='utf-8') as f:
                        json.dump(cookie, f, ensure_ascii=False, indent=4)
                    return cookie
            except Exception as e:
                last_error = f"Cookie生成失败(尝试{attempt+1}/10): {str(e)}"
                time.sleep(0.5)
        
        raise CookieGenerationError(
            f"无法获取有效Cookie\n"
            f"可能原因:\n"
            f"1. 网络连接问题\n"
            f"2. 番茄小说服务器限制\n"
            f"3. 文件权限问题\n"
            f"最后一次错误: {last_error}"
        )

    def get_book_info(self, book_id):
        url = f'https://fanqienovel.com/page/{book_id}'
        response = self.session.get(url, headers=self.get_headers())
        if response.status_code != 200:
            print(f"网络请求失败，状态码: {response.status_code}")
            return None, None, None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        name_element = soup.find('h1')
        name = name_element.text if name_element else "未知书名"
        
        author_name_element = soup.find('div', class_='author-name')
        author_name = None
        if author_name_element:
            author_name_span = author_name_element.find('span', class_='author-name-text')
            author_name = author_name_span.text if author_name_span else "未知作者"
        
        description_element = soup.find('div', class_='page-abstract-content')
        description = None
        if description_element:
            description_p = description_element.find('p')
            description = description_p.text if description_p else "无简介"
        
        return name, author_name, description

    def extract_chapters(self, book_id):
        url = f'https://api5-normal-lf.fqnovel.com/reading/bookapi/search/{book_id}/v'
        response = self.session.get(url, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')
        
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

    def down_text(self, chapter_id):
        if self.use_local_crawler:
            try:
                chapter = FanQieChapter(chapter_id, cookie=self.get_cookie())
                return chapter.get_paras().join_paras("    ")
            except Exception as e:
                raise ConnectionError(f"本地爬虫解析失败: {e}")

        max_retries = self.config.get('max_retries', 3)
        retry_count = 0
        content = ""

        while retry_count < max_retries:
            try:
                api_url = f"https://api.cengui.cn/api/tomato/content.php?item_id={chapter_id}"
                response = self.session.get(api_url, timeout=self.config["request_timeout"])
                data = response.json()

                if data.get("code") == 200:
                    content = data.get("data", {}).get("content", "")

                    content = re.sub(r'<header>.*?</header>', '', content, flags=re.DOTALL)
                    content = re.sub(r'<footer>.*?</footer>', '', content, flags=re.DOTALL)
                    content = re.sub(r'</?article>', '', content)
                    content = re.sub(r'<p idx="\d+">', '\n', content)
                    content = re.sub(r'</p>', '\n', content)
                    content = re.sub(r'<[^>]+>', '', content)
                    content = re.sub(r'\\u003c|\\u003e', '', content)

                    title = data.get("data", {}).get("title", "")
                    if title and content.startswith(title):
                        content = content[len(title):].lstrip()

                    content = re.sub(r'\n{2,}', '\n', content).strip()
                    content = '\n'.join(['    ' + line if line.strip() else line for line in content.split('\n')])
                    break
            except Exception as e:
                print(f"请求失败: {str(e)}, 重试第{retry_count + 1}次...")
                retry_count += 1
                time.sleep(1 * retry_count)

        if not content:
            raise ConnectionError(f"无法下载章节 {chapter_id}，API 可能已失效或网络错误。")

        return content
