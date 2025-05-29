import json
import re
import typing
from typing import List, Dict

import requests
from lxml import etree


class Paragraphs(list):
    """Helper list subclass for paragraphs."""

    def join_paras(self, para_starts: str = "    ") -> str:
        text = ""
        for para in self:
            text += para_starts + para + "\n"
        return text.rstrip("\n")


class FanQieChapDecoder:
    """Decoder for encrypted chapter text."""

    CODE_ST = 0xE3E8
    CODE_ED = 0xE55B
    charset: List[str] = [
        "D",
        "在",
        "主",
        "特",
        "家",
        "军",
        "然",
        "表",
        "场",
        "4",
        "要",
        "只",
        "v",
        "和",
        "?",
        "6",
        "别",
        "还",
        "g",
        "现",
        "儿",
        "岁",
        "?",
        "?",
        "此",
        "象",
        "月",
        "3",
        "出",
        "战",
        "工",
        "相",
        "o",
        "男",
        "首",
        "失",
        "世",
        "F",
        "都",
        "平",
        "文",
        "什",
        "V",
        "O",
        "将",
        "真",
        "T",
        "那",
        "当",
        "?",
        "会",
        "立",
        "些",
        "u",
        "是",
        "十",
        "张",
        "学",
        "气",
        "大",
        "爱",
        "两",
        "命",
        "全",
        "后",
        "东",
        "性",
        "通",
        "被",
        "1",
        "它",
        "乐",
        "接",
        "而",
        "感",
        "车",
        "山",
        "公",
        "了",
        "常",
        "以",
        "何",
        "可",
        "话",
        "先",
        "p",
        "i",
        "叫",
        "轻",
        "M",
        "士",
        "w",
        "着",
        "变",
        "尔",
        "快",
        "l",
        "个",
        "说",
        "少",
        "色",
        "里",
        "安",
        "花",
        "远",
        "7",
        "难",
        "师",
        "放",
        "t",
        "报",
        "认",
        "面",
        "道",
        "S",
        "?",
        "克",
        "地",
        "度",
        "I",
        "好",
        "机",
        "U",
        "民",
        "写",
        "把",
        "万",
        "同",
        "水",
        "新",
        "没",
        "书",
        "电",
        "吃",
        "像",
        "斯",
        "5",
        "为",
        "y",
        "白",
        "几",
        "日",
        "教",
        "看",
        "但",
        "第",
        "加",
        "候",
        "作",
        "上",
        "拉",
        "住",
        "有",
        "法",
        "r",
        "事",
        "应",
        "位",
        "利",
        "你",
        "声",
        "身",
        "国",
        "问",
        "马",
        "女",
        "他",
        "Y",
        "比",
        "父",
        "x",
        "A",
        "H",
        "N",
        "s",
        "X",
        "边",
        "美",
        "对",
        "所",
        "金",
        "活",
        "回",
        "意",
        "到",
        "z",
        "从",
        "j",
        "知",
        "又",
        "内",
        "因",
        "点",
        "Q",
        "三",
        "定",
        "8",
        "R",
        "b",
        "正",
        "或",
        "夫",
        "向",
        "德",
        "听",
        "更",
        "?",
        "得",
        "告",
        "并",
        "本",
        "q",
        "过",
        "记",
        "L",
        "让",
        "打",
        "f",
        "人",
        "就",
        "者",
        "去",
        "原",
        "满",
        "体",
        "做",
        "经",
        "K",
        "走",
        "如",
        "孩",
        "c",
        "G",
        "给",
        "使",
        "物",
        "?",
        "最",
        "笑",
        "部",
        "?",
        "员",
        "等",
        "受",
        "k",
        "行",
        "一",
        "条",
        "果",
        "动",
        "光",
        "门",
        "头",
        "见",
        "往",
        "自",
        "解",
        "成",
        "处",
        "天",
        "能",
        "于",
        "名",
        "其",
        "发",
        "总",
        "母",
        "的",
        "死",
        "手",
        "入",
        "路",
        "进",
        "心",
        "来",
        "h",
        "时",
        "力",
        "多",
        "开",
        "己",
        "许",
        "d",
        "至",
        "由",
        "很",
        "界",
        "n",
        "小",
        "与",
        "Z",
        "想",
        "代",
        "么",
        "分",
        "生",
        "口",
        "再",
        "妈",
        "望",
        "次",
        "西",
        "风",
        "种",
        "带",
        "J",
        "?",
        "实",
        "情",
        "才",
        "这",
        "?",
        "E",
        "我",
        "神",
        "格",
        "长",
        "觉",
        "间",
        "年",
        "眼",
        "无",
        "不",
        "亲",
        "关",
        "结",
        "0",
        "友",
        "信",
        "下",
        "却",
        "重",
        "己",
        "老",
        "2",
        "音",
        "字",
        "m",
        "呢",
        "明",
        "之",
        "前",
        "高",
        "P",
        "B",
        "目",
        "太",
        "e",
        "9",
        "起",
        "稜",
        "她",
        "也",
        "W",
        "用",
        "方",
        "子",
        "英",
        "每",
        "理",
        "便",
        "西",
        "数",
        "期",
        "中",
        "C",
        "外",
        "样",
        "a",
        "海",
        "们",
        "任",
    ]

    def interpreter(self, cc: int) -> str:
        if self.CODE_ST <= cc <= self.CODE_ED:
            bias = cc - self.CODE_ST
            if self.charset[bias] == "?":
                return chr(cc)
            return self.charset[bias]
        return chr(cc)

    def decode(self, content: str) -> str:
        result = ""
        for ch in content:
            result += self.interpreter(ord(ch))
        return result


class FanQieChapter:
    """Fetch and decode a FanQie chapter."""

    headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": "",
    }

    def __init__(self, chap_id: int, cookie: str = "") -> None:
        self.chap_id = int(chap_id)
        self.chapter_url = f"https://fanqienovel.com/reader/{self.chap_id}"
        if cookie:
            self.headers["Cookie"] = cookie
        self.decoder = FanQieChapDecoder()

    def get_api_data(self) -> Dict:
        response = requests.get(self.chapter_url, headers=self.headers)
        tree = etree.HTML(response.text)
        js = tree.xpath("//html/body/script[1]/text()")[0]
        api_data = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?});", js, re.DOTALL).group(1)
        api_data = {"data": json.loads(api_data)["reader"]}
        return api_data

    def get_decoded_html(self) -> List[dict]:
        json_obj = self.get_api_data()
        content = json_obj["data"]["chapterData"]["content"]
        parser = etree.HTMLParser()
        tree = etree.fromstring(f"<root>{content}</root>", parser)
        result = []
        for element in tree.xpath("//*"):
            if element.tag == "p" and not element.get("class"):
                if element.text:
                    result.append({"type": "p", "content": self.decoder.decode(element.text)})
            elif element.tag == "img":
                if element.get("src", "").startswith("http"):
                    result.append(
                        {
                            "type": "i",
                            "src": element.get("src", ""),
                            "alt": element.get("alt", ""),
                            "width": element.get("width", ""),
                            "height": element.get("height", ""),
                        }
                    )
        return result

    def get_paras(self) -> Paragraphs:
        content = []
        for i in self.get_decoded_html():
            if i["type"] == "p":
                content.append(i["content"])
        return Paragraphs(content)


class BookError(Exception):
    pass


class FanQieBook:
    """书籍相关"""

    headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def __init__(self, book_id: typing.Union[int, str]) -> None:
        self.book_id = int(book_id)
        self.book_url = "https://fanqienovel.com/page/" + str(book_id)

    def get_chap_ids(self) -> typing.List[int]:
        response = requests.get(url=self.book_url, headers=self.headers)
        tree = etree.HTML(response.text)
        try:
            chaps = tree.xpath('//div[@class="chapter-item"]/a[@class="chapter-item-title"]/@href')
        except AttributeError:
            raise BookError("过段时间后重试")
        return [int(i.split('/')[-1]) for i in chaps]

    def get_chap_titles(self) -> typing.List[str]:
        response = requests.get(url=self.book_url, headers=self.headers)
        tree = etree.HTML(response.text)
        try:
            chaps = tree.xpath('//div[@class="chapter-item"]/a[@class="chapter-item-title"]/text()')
        except AttributeError:
            raise BookError("过段时间后重试")
        return chaps

    def get_info(self) -> dict:
        info = {}
        response = requests.get(url=self.book_url, headers=self.headers)
        tree = etree.HTML(response.text)
        info["title"] = tree.xpath('//div[@class="info-name"]/h1/text()')[0]
        info["author"] = tree.xpath('//span[@class="author-name-text"]/text()')[0]
        info["cover"] = json.loads(tree.xpath("//html/head/script[1]/text()")[0])["image"][0]
        info["intro"] = tree.xpath('//div[@class="page-abstract-content"]/p/text()')[0]
        info["labels"] = tree.xpath('//div[@class="info-label"]/span/text()')
        info["word_count"] = " ".join(tree.xpath('//div[@class="info-count-word"]/span/text()'))
        info["last_update_time"] = tree.xpath('//span[@class="info-last-time"]/text()')[0]
        return info

    def get_volumes(self) -> typing.List[typing.Tuple[str, int, int]]:
        volumes = {}
        response = requests.get(url=self.book_url, headers=self.headers)
        tree = etree.HTML(response.text)
        volume_info = tree.xpath('//div[@class="volume volume_first"]/text()')
        volumes[volume_info[0]] = int(volume_info[2])
        volume_info = tree.xpath('//div[@class="volume"]/text()')
        temp_info = []
        for i, j in enumerate(volume_info):
            if i % 4 == 0:
                temp_info.append(j)
            elif i % 4 == 2:
                temp_info.append(int(j))
            elif i % 4 == 3:
                volumes[temp_info[0]] = temp_info[1]
                temp_info = []
        vols_list = []
        count = 0
        for i, j in zip(volumes.keys(), volumes.values()):
            vols_list.append((i, count + 1, count + j))
            count += j
        if len(vols_list) == 1 and vols_list[0][0] == "第一卷":
            return []
        return vols_list


class FanQieBookSearcher:
    """搜索书籍相关"""

    headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def filters(self, page: int = 0, gender: int = -1, category_id: int = -1, creation_status: int = -1, word_count: int = -1, sort: int = -1) -> dict:
        api_url = f"https://fanqienovel.com/api/author/library/book_list/v0/?page_count=18&page_index={page}&gender={gender}&category_id={category_id}&creation_status={creation_status}&word_count={word_count}&book_type=-1&sort={sort}"
        response = requests.get(url=api_url, headers=self.headers)
        return response.json()["data"]

    def search(self, query_word: str, page: int = 0, query_type: int = 0, update_time: int = 127, word_count: int = 127, creation_status: int = 127) -> dict:
        api_url = f"https://fanqienovel.com/api/author/search/search_book/v1?filter={update_time}%2C{word_count}%2C{creation_status}%2C127&page_count=10&page_index={page}&query_type={query_type}&query_word={query_word}"
        response = requests.get(url=api_url, headers=self.headers)
        return {
            "book_list": response.json()["data"]["search_book_data_list"],
            "total_count": response.json()["data"]["total_count"],
        }

    def get_category_list(self, gender: int = -1) -> list:
        api_url = f"https://fanqienovel.com/api/author/book/category_list/v0/?gender={gender}"
        response = requests.get(url=api_url, headers=self.headers)
        return response.json()["data"]


class FanQieEbook:
    """下载书籍成电子书格式"""

    def __init__(self, book_id: typing.Union[int, str], cookie: str = "", fallback: typing.Callable = lambda t, c: None) -> None:
        self.book_object = FanQieBook(book_id)
        self.cookie = cookie
        self.fallback = fallback

    def epub(self, path: str) -> None:
        from ebooklib import epub
        book = epub.EpubBook()
        self.fallback("epub", ["metadata"])
        book_info = self.book_object.get_info()
        book.set_identifier(str(self.book_object.book_id))
        book.set_title(book_info["title"])
        book.set_language("zh")
        book.add_author(book_info["author"])
        [book.add_metadata("DC", "subject", i) for i in book_info["labels"]]
        book.add_metadata("DC", "description", book_info["intro"])
        book.add_metadata("DC", "date", book_info["last_update_time"].replace(" ", "T") + "+08:00")
        book.set_cover(file_name="cover.jpg", content=requests.get(book_info["cover"]).content)

        html_template = """
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml">
          <head>
            <meta charset="utf-8"/>
            <title>{title}</title>
          </head>
          <body>
            {content}
          </body>
        </html>
        """

        chapter_item_list = []
        self.fallback("epub", ["ready"])
        chapter_ids = self.book_object.get_chap_ids()
        volumes = self.book_object.get_volumes()
        for n, i in enumerate(chapter_ids, 1):
            chapter = FanQieChapter(i, cookie=self.cookie)
            title = chapter.get_title()
            self.fallback("epub", ["chapter", title, n, len(chapter_ids)])
            chapter_item = epub.EpubHtml(title=title, file_name=f"chap_{n}.xhtml", lang="zh")
            for j in chapter.get_decoded_html():
                if j["type"] == "p":
                    html_content += f"<p>{j['content']}</p>\n"
                elif j["type"] == "i":
                    img_content = requests.get(j["src"]).content
                    md5 = j["src"].split("/")[-1].split("?")[0].split("~")[0]
                    image_item = epub.EpubItem(uid=md5, file_name=f"images/{md5}.jpg", media_type="image/jpeg", content=img_content)
                    book.add_item(image_item)
                    html_content += f"<img src=\"images/{md5}.jpg\" alt='{j['alt']}' width='{j['width']}' height='{j['height']}'>\n"
            chapter_item.content = html_template.format(title=title, content=html_content)
            chapter_item_list.append(chapter_item)
            book.add_item(chapter_item)

        self.fallback("epub", ["volumes"])
        if not volumes:
            book.toc = chapter_item_list
        else:
            book.toc = tuple(((i[0], chapter_item_list[i[1] - 1 : i[2]]) for i in volumes))
        book.spine = ["nav"] + chapter_item_list
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        self.fallback("epub", ["write"])
        epub.write_epub(path, book, {})
        self.fallback("epub", ["done"])

