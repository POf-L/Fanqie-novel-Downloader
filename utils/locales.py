# -*- coding: utf-8 -*-
"""
Language Configuration / 语言配置文件
"""

import os
import sys
import json

DEFAULT_LANG = "zh"

def _get_config_file():
    """获取配置文件路径"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    config_dir = os.path.join(base_dir, 'config')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'fanqie_novel_downloader_config.json')

def get_current_lang():
    """从配置文件读取当前语言设置"""
    try:
        config_file = _get_config_file()
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('language', DEFAULT_LANG)
    except:
        pass
    return DEFAULT_LANG

def set_current_lang(lang):
    """保存语言设置到配置文件"""
    try:
        config_file = _get_config_file()
        config = {}
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        config['language'] = lang
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

MESSAGES = {
    "zh": {
        "dl_search_error": "搜索异常: {}",
        "dl_detail_error": "获取书籍详情异常: {}",
        "dl_chapter_list_start": "[DEBUG] 开始获取章节列表: ID={}",
        "dl_chapter_list_resp": "[DEBUG] 章节列表响应: {}",
        "dl_chapter_list_error": "获取章节列表异常: {}",
        "dl_content_error": "获取章节内容异常: {}",
    },
    "en": {
        "dl_search_error": "Search error: {}",
        "dl_detail_error": "Get book detail error: {}",
        "dl_chapter_list_start": "[DEBUG] Start fetching chapters: ID={}",
        "dl_chapter_list_resp": "[DEBUG] Chapter list response: {}",
        "dl_chapter_list_error": "Get chapter list error: {}",
        "dl_content_error": "Get chapter content error: {}",
    }
}

def t(key, *args):
    """Get translated string"""
    lang_code = get_current_lang()
    if lang_code not in MESSAGES:
        lang_code = "zh"
    
    lang_dict = MESSAGES.get(lang_code, {})
    
    if key not in lang_dict:
        msg = MESSAGES.get("zh", {}).get(key, key)
    else:
        msg = lang_dict[key]
    
    if args:
        try:
            return msg.format(*args)
        except Exception:
            return msg
    return msg
