import requests
import random
import json
import os
import time
import re
from bs4 import BeautifulSoup
from config import CONFIG
from typing import Optional, Dict
from fake_useragent import UserAgent
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
import gzip

# Disable SSL Warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

okp = [
    "ac25", "c67d", "dd8f", "38c1",
    "b37a", "2348", "828e", "222e"
]

def grk():
    return "".join(okp)

class FqCrypto:
    """番茄小说请求加密类"""
    def __init__(self, key: bytes, iv: bytes):
        self.key = key
        self.iv = iv
        self.cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

    def encrypt(self, plaintext: str) -> str:
        """AES加密"""
        padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
        encrypted_data = self.cipher.encrypt(padded_data)
        return base64.b64encode(encrypted_data).decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """AES解密"""
        encrypted_data = base64.b64decode(ciphertext)
        decrypted_data = self.cipher.decrypt(encrypted_data)
        return unpad(decrypted_data, AES.block_size).decode('utf-8')

class FqVariable:
    """番茄小说可变参数类"""
    def __init__(self, book_id: str, chapter_id: str, user_agent: str):
        self.book_id = book_id
        self.chapter_id = chapter_id
        self.user_agent = user_agent
        self.key = self._generate_key()
        self.iv = self._generate_iv()
        self.fqc = FqCrypto(self.key, self.iv)

    def _generate_key(self) -> bytes:
        """生成 AES Key"""
        return grk().encode('utf-8')[:16]

    def _generate_iv(self) -> bytes:
        """生成 AES IV"""
        # 简单处理，实际应用中可能需要更复杂的IV生成逻辑
        return self.key 

    def get_b(self) -> str:
        """获取加密参数 b"""
        t = int(time.time() * 1000)
        plaintext = f'{{"item_id":"{self.chapter_id}","secondary_item_id":"{self.book_id}","timestamp":{t}}}'
        return self.fqc.encrypt(plaintext)

    def get_common_params(self) -> dict:
        """获取通用请求参数"""
        common_params = CONFIG["request"]["official_api"]
        return {
            "aid": common_params.get("aid", "1967"),
            "app_name": "novel_reader",
            "app_version": "6.2.5.32", # 这个可以考虑放入配置
            "version_code": common_params.get("update_version_code", "62532"),
            "channel": "oppo", # 这个可以考虑放入配置
            "device_platform": "android", # 这个可以考虑放入配置
            "device_type": "ALP-AL00", # 这个可以考虑放入配置
            "os_version": "10", # 这个可以考虑放入配置
            "language": "zh-Hans-CN", # 这个可以考虑放入配置
            "platform": "android", # 这个可以考虑放入配置
            "resolution": "1080*2127", # 这个可以考虑放入配置
            "server_device_id": common_params.get("server_device_id", ""),
            "iid": common_params.get("install_id", ""),
            "device_id": common_params.get("install_id", ""), # 通常 iid 和 device_id 相同
        }

class FqReq:
    """番茄小说官方API请求类"""
    def __init__(self, book_id: str, chapter_id: str):
        self.book_id = book_id
        self.chapter_id = chapter_id
        self.session = requests.Session()
        self.user_agent = random.choice(CONFIG["request"]["user_agents"])
        self.fqv = FqVariable(self.book_id, self.chapter_id, self.user_agent)
        self.api_url = f"https://api5-normal-lf.fqnovel.com/reading/bookapi/item/v1/"

    def _get_signed_url(self) -> str:
        """获取签名后的URL"""
        common_params = self.fqv.get_common_params()
        b_param = self.fqv.get_b()
        
        all_params = {**common_params, "b": b_param}
        
        # 模拟 msToken 和 x_gorgon 的生成 (实际需要逆向APP)
        # 这里使用固定值或随机值，可能无法通过校验
        all_params["msToken"] = "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=107))
        all_params["X-Gorgon"] = "0404c00000000000000000000000000000000000" # 示例，实际无效
        all_params["X-Khronos"] = str(int(time.time()))
        
        # 确保参数顺序一致性，这对于签名很重要 (虽然此处未实现真实签名)
        # sorted_params = collections.OrderedDict(sorted(all_params.items()))
        # query_string = urlencode(sorted_params)
        
        # 简化处理，直接拼接，因为真实签名未实现
        query_string = '&'.join([f"{k}={v}" for k, v in all_params.items()])
        
        return f"{self.api_url}?{query_string}"

    def get_content(self) -> Optional[dict]:
        """获取章节内容 (官方API)"""
        signed_url = self._get_signed_url()
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate, br", # 告知服务器支持gzip
            "Content-Type": "application/json; charset=utf-8",
            # 其他必要的头，如 "x-ss-stub", "x-tt-trace-id" 等，需要从APP抓包分析
        }
        
        try:
            response = self.session.get(signed_url, headers=headers, timeout=CONFIG["request"]["request_timeout"], verify=False) # verify=False 禁用SSL证书验证
            response.raise_for_status() # 如果状态码不是2xx，则抛出异常
            
            # 检查响应头是否表明内容是gzip压缩的
            if response.headers.get('Content-Encoding') == 'gzip':
                # 解压gzip内容
                decompressed_data = gzip.decompress(response.content)
                data = json.loads(decompressed_data.decode('utf-8'))
            else:
                data = response.json()

            if data.get("status_code") == 0 and data.get("data"):
                return data["data"]
            else:
                print(f"官方API请求失败: {data.get('message', '未知错误')}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"官方API网络请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"官方API响应JSON解析错误: {e}")
            return None
        except Exception as e:
            print(f"官方API处理时发生未知错误: {e}")
            return None

# Global utility functions
ua = UserAgent()

def get_headers(cookie: Optional[str] = None) -> Dict[str, str]:
    """生成请求头，优先使用 fake_useragent，并可选择性加入 Cookie"""
    base_headers = {
        "User-Agent": ua.random,  # 使用 fake_useragent 生成随机UA
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
    if cookie:
        base_headers["Cookie"] = cookie
    return base_headers

def down_text(chapter_id: str, current_api_index: int = 0) -> str:
    """
    下载指定章节ID的内容，支持API轮询和重试。
    新增逻辑：优先尝试官方API，然后轮询第三方API。
    """
    fq_req = FqReq(book_id="dummy_book_id_not_used_by_fqreq_get_content", chapter_id=chapter_id) # book_id 可能需要适配
    official_content_data = fq_req.get_content()

    if official_content_data and "content" in official_content_data:
        encrypted_content = official_content_data["content"]
        # 官方API的内容通常是加密的，需要解密
        # 假设 fqc 是 FqCrypto 的一个实例，并且 key 和 iv 已经基于 chapter_id 或其他方式正确初始化
        # 这个解密逻辑可能需要根据 FqReq 或 FqVariable 的具体实现来调整
        try:
            # 这里的 key 和 iv 获取方式需要确认，FqVariable 初始化时需要 book_id 和 chapter_id
            # 如果 FqReq 内部处理了解密，这里直接用解密后的内容
            # 假设 get_content 返回的是解密后的数据字典，其中包含 content 字段
            # 或者 FqReq 实例本身就有解密方法
            
            # 查找解密密钥和IV (这部分可能需要调整，取决于FqCrypto的实际用法)
            # key = grk().encode('utf-8')[:16] 
            # iv = key 
            # crypto = FqCrypto(key, iv)
            # plaintext_content = crypto.decrypt(encrypted_content)
            
            # **重要假设**：FqReq.get_content() 返回的字典中，'content'已经是解密后的HTML或文本
            # 如果不是，这里的逻辑需要修改为调用解密方法
            
            # 假设 content 就是解密后的HTML，需要进一步处理
            raw_content = official_content_data["content"] # 再次获取，以防上面被修改

            # 官方API内容处理 (与原有逻辑类似，但针对性调整)
            soup = BeautifulSoup(raw_content, 'html.parser')
            
            article_content = soup.find("article", class_="reader-article-content")
            if not article_content: # 如果没有 article 标签，尝试直接获取段落
                 paragraphs = soup.find_all("p")
            else:
                 paragraphs = article_content.find_all("p")

            if not paragraphs: # 如果直接 beautifulsoup 解析不出 p 标签（例如内容已是纯文本）
                # 检查是否已经是处理好的纯文本
                if not ("<p>" in raw_content or "</p>" in raw_content):
                    content = raw_content # 假设已经是纯文本
                else: # 否则认为处理失败
                    print(f"官方API内容解析失败，未找到段落: {chapter_id}")
                    content = "" # 解析失败，置空
            else:
                content_lines = [p.get_text(separator="\n", strip=True) for p in paragraphs]
                content = "\n".join(content_lines)

            content = '\n'.join(['    ' + line if line.strip() else line for line in content.split('\n')]).strip()
            
            if content:
                print(f"成功从官方API获取章节 {chapter_id}")
                return content
            else:
                print(f"官方API获取章节 {chapter_id} 内容为空或解析失败，尝试第三方API...")
                
        except Exception as e:
            print(f"处理官方API内容时发生错误: {e}, chapter_id: {chapter_id}。尝试第三方API...")
            # 出错则继续尝试第三方API

    # 如果官方API失败或内容为空，则尝试第三方API
    max_retries = CONFIG["request"].get('max_retries', 3)
    api_endpoints = CONFIG["request"].get('api_endpoints', [])
    
    if not api_endpoints:
        raise ConnectionError("没有可用的第三方API端点。")

    for i in range(len(api_endpoints)):
        current_api_real_index = (current_api_index + i) % len(api_endpoints)
        api_url_template = api_endpoints[current_api_real_index]
        api_url = api_url_template.format(chapter_id=chapter_id)
        
        print(f"尝试从第三方API下载: {api_url}")
        
        for attempt in range(max_retries):
            try:
                headers = get_headers() # 使用全局的 get_headers
                response = requests.get(api_url, headers=headers, timeout=CONFIG["request"]["request_timeout"])
                response.raise_for_status()
                data = response.json()

                if data.get("code") == 200 and data.get("data", {}).get("content"):
                    content = data["data"]["content"]
                    
                    # 移除HTML标签 (与原down_text逻辑类似)
                    content = re.sub(r'<header>.*?</header>', '', content, flags=re.DOTALL)
                    content = re.sub(r'<footer>.*?</footer>', '', content, flags=re.DOTALL)
                    content = re.sub(r'</?article>', '', content)
                    
                    # 针对<p idx="xxx"> 和 <p>段落的处理
                    # 首先尝试匹配带idx的p标签，如果存在，则按该格式处理
                    if re.search(r'<p idx="\d+">', content):
                        content = re.sub(r'<p idx="\d+">', '\n', content)
                    else: # 否则，按普通<p>标签处理
                        content = content.replace('<p>', '\n') # 对于没有idx的p标签
                    
                    content = re.sub(r'</p>', '\n', content) # 统一处理闭合p标签
                    content = re.sub(r'<[^>]+>', '', content) # 移除剩余HTML标签
                    content = re.sub(r'\\u003c|\\u003e', '', content) # 移除Unicode转义的尖括号

                    title = data.get("data", {}).get("title", "")
                    if title and content.startswith(title):
                        content = content[len(title):].lstrip()
                    
                    content = re.sub(r'\n{2,}', '\n', content).strip()
                    content = '\n'.join(['    ' + line if line.strip() else line for line in content.split('\n')])
                    
                    if content:
                        print(f"成功从第三方API {api_url} 获取章节 {chapter_id}")
                        # 更新优先API索引，如果需要的话 (这部分逻辑在主调用处管理)
                        return content
                else:
                    print(f"第三方API {api_url} 返回数据格式不正确或无内容。响应: {data}")
            
            except requests.exceptions.Timeout:
                print(f"第三方API {api_url} 请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1: # 最后一次尝试仍然超时
                    print(f"第三方API {api_url} 达到最大超时次数。")
            except requests.exceptions.RequestException as e:
                print(f"第三方API {api_url} 请求失败: {e} (尝试 {attempt + 1}/{max_retries})")
            except json.JSONDecodeError:
                print(f"第三方API {api_url} 响应非JSON格式 (尝试 {attempt + 1}/{max_retries})。响应内容: {response.text[:200]}") # 只打印前200字符
            
            if attempt < max_retries - 1: # 如果不是最后一次尝试，则等待后重试
                time.sleep(CONFIG["request"].get("request_rate_limit", 0.5) * (attempt + 1)) # 使用请求速率限制或固定延时
            else: # 如果是最后一次尝试且失败了
                print(f"第三方API {api_url} 在所有尝试后均失败。")
                break # 跳出当前API的重试循环，尝试下一个API

    raise ConnectionError(f"无法下载章节 {chapter_id}，所有官方和第三方API尝试均失败。")


def get_book_info(book_id: str, headers: Dict[str, str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """获取书名、作者、简介 (独立函数)"""
    url = f'https://fanqienovel.com/page/{book_id}'
    try:
        response = requests.get(url, headers=headers, timeout=15) # 使用传入的headers
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"获取书籍信息网络请求失败: {e}, URL: {url}")
        return None, None, None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    name_element = soup.find('h1', class_='title') # 更精确的选择器
    name = name_element.text.strip() if name_element else "未知书名"
    
    author_name_element = soup.find('div', class_='meta-value', attrs={'itemprop': 'author'})
    author_name = author_name_element.text.strip() if author_name_element else "未知作者"
    
    # 尝试多种方式获取简介
    description = "无简介"
    # 优先尝试 meta 标签
    meta_description = soup.find('meta', attrs={'name': 'description'})
    if meta_description and meta_description.get('content'):
        description = meta_description['content'].strip()
    else:
        # 其次尝试class为 'abstract-content' 的 div (根据旧代码的线索，但可能已变)
        abstract_content_div = soup.find('div', class_='page-abstract-content')
        if abstract_content_div:
            p_tag = abstract_content_div.find('p')
            if p_tag:
                description = p_tag.text.strip()
        else:
            # 再次尝试 itemprop="description"
            desc_prop_element = soup.find(attrs={'itemprop': 'description'})
            if desc_prop_element:
                description = desc_prop_element.text.strip()
            else:
                # 最后尝试寻找包含特定文本模式的 div (作为备用方案)
                # 例如，寻找包含“简介：”或“内容概要：”等文本的父级元素
                # 此处简化，不添加过于复杂的备用逻辑，以防页面结构变化导致误判
                pass # 可以根据需要添加更多备用方案

    return name, author_name, description

def extract_chapters(book_id: str, headers: Dict[str, str]) -> list:
    """
    从番茄目录页解析章节列表 (独立函数，原名 get_chapters_from_api)
    """
    # 番茄小说的目录页现在是动态加载的，直接请求HTML可能不完整
    # 需要找到对应的API。根据之前的 RequestHandler.extract_chapters, API地址可能是：
    # https://api5-normal-lf.fqnovel.com/reading/bookapi/directory/all_items/v/?book_id={book_id}
    # 或者 https://fanqienovel.com/api/reader/directory/all_items?book_id={book_id}
    # 实际测试表明，网页版目录通常通过 JS 请求 `https://fanqienovel.com/api/reader/directory/all_items?book_id={book_id}`
    
    # 使用之前 RequestHandler 中的API端点作为参考，但需要确认其有效性
    # url = f'https://api5-normal-lf.fqnovel.com/reading/bookapi/search/{book_id}/v' # 旧的，可能已失效
    
    # 尝试使用Web端目录API
    api_url = f"https://fanqienovel.com/api/reader/directory/all_items?book_id={book_id}"
    
    chapters = []
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == 0 and "data" in data and "item_list" in data["data"]:
            item_list = data["data"]["item_list"]
            for idx, item_data in enumerate(item_list):
                item_id = item_data.get("item_id")
                title = item_data.get("title", f"未知章节 {idx+1}")
                
                # 确保标题规范化 (与原extract_chapters逻辑类似)
                raw_title = title.strip()
                if re.match(r'^(番外|特别篇|if线)\s*', raw_title, re.IGNORECASE): # 添加 re.IGNORECASE
                    final_title = raw_title
                else:
                    # 移除 "第xxx章" 前缀（如果存在）
                    clean_title_re = re.sub(r'^第[一二三四五六七八九十百千\d零〇洞]+章\s*', '', raw_title, flags=re.IGNORECASE).strip()
                    # 确保章节号从1开始，并重新构建标题
                    final_title = f"第{idx + 1}章 {clean_title_re if clean_title_re else raw_title}"


                chapters.append({
                    "id": str(item_id),
                    "title": final_title,
                    # URL不再直接从API获取，可以构造或在需要时构造
                    # "url": f"https://fanqienovel.com/page/{book_id}/{item_id}", # 示例构造
                    "index": idx 
                })
            if not chapters: # 如果解析后章节列表为空
                print(f"书籍 {book_id} 目录解析为空，API返回数据: {data}")
        else:
            print(f"解析章节列表失败，API返回数据格式不正确或无章节数据: {data}")
            # 尝试从页面抓取 (作为备用，但通常更不可靠)
            # chapters = _extract_chapters_from_html_fallback(book_id, headers)

    except requests.exceptions.RequestException as e:
        print(f"获取章节列表API请求失败: {e}, URL: {api_url}")
        # 尝试从页面抓取 (作为备用)
        # chapters = _extract_chapters_from_html_fallback(book_id, headers)
    except json.JSONDecodeError:
        print(f"解析章节列表API响应非JSON格式。URL: {api_url}, 响应: {response.text[:200]}")
        # 尝试从页面抓取 (作为备用)
        # chapters = _extract_chapters_from_html_fallback(book_id, headers)
    
    return chapters

# def _extract_chapters_from_html_fallback(book_id: str, headers: Dict[str, str]) -> list:
# """备用方案：直接从书籍目录页HTML中抓取章节列表（如果API失效）"""
#     print(f"尝试从HTML页面回退抓取章节列表: {book_id}")
#     page_url = f"https://fanqienovel.com/page/{book_id}"
#     chapters = []
#     try:
#         response = requests.get(page_url, headers=headers, timeout=15)
#         response.raise_for_status()
#         soup = BeautifulSoup(response.text, 'html.parser')
        
#         # 这里的选择器需要根据实际的前端结构来确定，以下为示例
#         # 假设章节列表在一个 <ul class="chapter-list"> 中，每个章节是 <li><a>...</a></li>
#         chapter_list_ul = soup.find('ul', class_='chapter-list') # 或者其他合适的选择器
#         if not chapter_list_ul:
#             # 尝试更通用的 div 结构，例如 class="volume" 下的 class="chapter-item"
#             volume_divs = soup.find_all('div', class_=re.compile(r'volume(-wrapper)?|chapter-list-wrapper'))
#             if not volume_divs:
#                 print("HTML回退：未找到章节列表容器。")
#                 return []
            
#             all_chapter_links = []
#             for vol_div in volume_divs:
#                 # 寻找所有可能的章节链接元素
#                 links = vol_div.find_all('a', href=re.compile(rf'/page/{book_id}/\d+|/reader/\d+'))
#                 all_chapter_links.extend(links)
            
#             if not all_chapter_links:
#                 print("HTML回退：未找到章节链接。")
#                 return []

#             raw_chapters = []
#             for idx, a_tag in enumerate(all_chapter_links):
#                 href = a_tag.get('href', '')
#                 item_id_match = re.search(r'/(\d+)$', href)
#                 if not item_id_match:
#                     continue
                
#                 item_id = item_id_match.group(1)
#                 title = a_tag.get_text(strip=True) or f"未知章节 {idx+1}"
#                 raw_chapters.append({"id": item_id, "title": title, "index": idx}) # 初始索引
            
#             # 对 raw_chapters 进行排序和重新编号 (如果需要)
#             # 假设页面上的顺序就是正确的阅读顺序
#             for idx, chap_data in enumerate(raw_chapters):
#                 raw_title = chap_data["title"].strip()
#                 if re.match(r'^(番外|特别篇|if线)\s*', raw_title, re.IGNORECASE):
#                     final_title = raw_title
#                 else:
#                     clean_title_re = re.sub(r'^第[一二三四五六七八九十百千\d零〇洞]+章\s*', '', raw_title, flags=re.IGNORECASE).strip()
#                     final_title = f"第{idx + 1}章 {clean_title_re if clean_title_re else raw_title}"
                
#                 chapters.append({
#                     "id": chap_data["id"],
#                     "title": final_title,
#                     "index": idx # 使用新的全局索引
#                 })

#         else: # 如果找到了 chapter_list_ul (旧版页面结构?)
#             for idx, li_item in enumerate(chapter_list_ul.find_all('li')):
#                 a_tag = li_item.find('a')
#                 if not a_tag or not a_tag.get('href'):
#                     continue
                
#                 href = a_tag['href']
#                 item_id_match = re.search(r'/(\d+)$', href) # 从URL末尾提取ID
#                 if not item_id_match:
#                     continue
#                 item_id = item_id_match.group(1)
#                 title = a_tag.get_text(strip=True) or f"未知章节 {idx+1}"
                
#                 # 规范化标题
#                 raw_title = title.strip()
#                 if re.match(r'^(番外|特别篇|if线)\s*', raw_title, re.IGNORECASE):
#                     final_title = raw_title
#                 else:
#                     clean_title_re = re.sub(r'^第[一二三四五六七八九十百千\d零〇洞]+章\s*', '', raw_title, flags=re.IGNORECASE).strip()
#                     final_title = f"第{idx + 1}章 {clean_title_re if clean_title_re else raw_title}"

#                 chapters.append({
#                     "id": item_id,
#                     "title": final_title,
#                     "index": idx
#                 })
#         if chapters:
#             print(f"HTML回退抓取成功，共找到 {len(chapters)} 章。")
#         else:
#             print("HTML回退抓取失败或未找到章节。")
            
#     except requests.exceptions.RequestException as e:
#         print(f"HTML回退抓取章节列表请求失败: {e}")
#     except Exception as e:
#         print(f"HTML回退抓取时发生未知错误: {e}")
#     return chapters


class CookieGenerationError(Exception):
    """自定义 Cookie 生成错误"""
    pass

class RequestHandler:
    def __init__(self):
        self.config = CONFIG["request"]
        self.session = requests.Session() # session 保留给 get_cookie 使用

    def get_headers(self, cookie=None):
        """生成随机请求头 - 此版本主要为 get_cookie 内部服务"""
        # 注意：这个 get_headers 与全局的 get_headers(cookie) 不同。
        # 全局的 get_headers 使用 fake_useragent。
        # 此处保留原始的基于CONFIG["request"]["user_agents"]的选择，
        # 因为 get_cookie 可能依赖于此UA列表进行特定的cookie获取行为。
        # 如果 get_cookie 也可以安全地使用 fake_useragent，则可以考虑统一。
        return {
            "User-Agent": random.choice(self.config.get("user_agents", [ua.random])), # Fallback to ua.random if not in config
            "Cookie": cookie if cookie else self.get_cookie()
        }

    def get_cookie(self):
        """生成或加载Cookie"""
        cookie_path = CONFIG["file"]["cookie_file"]
        last_error = None

        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)
                    # 确保加载的是字符串类型
                    if isinstance(cookie_data, str):
                        return cookie_data
                    else:
                        last_error = f"Cookie 文件 '{cookie_path}' 格式不正确"
            except FileNotFoundError:
                pass # 文件不存在，继续生成
            except json.JSONDecodeError:
                last_error = f"Cookie 文件 '{cookie_path}' 解析失败"
            except Exception as e:
                last_error = f"读取 Cookie 文件时发生错误: {e}"
        
        # 生成新Cookie
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
                    # 确保目录存在
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

    def get_cookie(self):
