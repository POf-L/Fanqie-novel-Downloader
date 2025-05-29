import json,re,requests
from lxml import etree


class Paragraphs(list):
    def join_paras(self,p="    "):
        return "".join(p+i+"\n" for i in self)[:-1]


class FanQieChapDecoder:
    CODE_ST=0xE3E8
    CODE_ED=0xE55B
    charset=list("D在主特家军然表场4要只v和?6别还g现儿岁??此象月3出战工相o男首失世F都平文什VO将真T那当?会立些u是十张学气大爱两命全后东性通被1它乐接而感车山公了常以何可话先pi叫轻M士w着变尔快l个说少色里安花远7难师放t报认面道S?克地度I好机U民写把万同水新没书电吃像斯5为y白几日教看但第加候作上拉住有法r事应位利你声身国问马女他Y比父xAHNsX边美对所金活回意到z从j知又内因点Q三定8Rb正或夫向德听更?得告并本q过记L让打f人就者去原满体做经K走如孩cG给使物?最笑部?员等受k行一条果动光门头见往自解成处天能于名其发总母的死手入路进心来h时力多开己许d至由很界n小与Z想代么分生口再妈望次西风种带J?实情才这?E我神格长觉间年眼无不亲关结0友信下却重己老2音字m呢明之前高PB目太e9起稜她也W用方子英每理便西数期中C外样a海们任")

    def interpreter(self, cc):
        if self.CODE_ST <= cc <= self.CODE_ED:
            bias = cc - self.CODE_ST
            if self.charset[bias] == "?":
                return chr(cc)
            return self.charset[bias]
        return chr(cc)

    def decode(self, content):
        result = ""
        for ch in content:
            result += self.interpreter(ord(ch))
        return result


class FanQieChapter:
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": "",
    }

    def __init__(self, chap_id, cookie=""):
        self.chap_id = int(chap_id)
        self.chapter_url = f"https://fanqienovel.com/reader/{self.chap_id}"
        if cookie:
            self.headers["Cookie"] = cookie
        self.decoder = FanQieChapDecoder()

    def get_api_data(self):
        response = requests.get(self.chapter_url, headers=self.headers)
        tree = etree.HTML(response.text)
        js = tree.xpath("//html/body/script[1]/text()")[0]
        api_data = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?});", js, re.DOTALL).group(1)
        api_data = {"data": json.loads(api_data)["reader"]}
        return api_data

    def get_decoded_html(self):
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

    def get_paras(self):
        content = []
        for i in self.get_decoded_html():
            if i["type"] == "p":
                content.append(i["content"])
        return Paragraphs(content)
