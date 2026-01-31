# -*- coding: utf-8 -*-
"""
API管理器 - 番茄小说官方API对接

该模块拆分为多个文件以控制单文件行数：
- core/api_manager_core.py
- core/api_manager_books.py
- core/api_manager_content.py
"""

from __future__ import annotations

import urllib3
import requests

try:
    from utils.packaging_fixes import apply_all_fixes
    apply_all_fixes()
except ImportError:
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

from .api_manager_core import APIManagerCoreMixin
from .api_manager_books import APIManagerBooksMixin
from .api_manager_content import APIManagerContentMixin


class APIManager(APIManagerCoreMixin, APIManagerBooksMixin, APIManagerContentMixin):
    """番茄小说官方API统一管理器"""


# 全局API管理器实例
api_manager = None


def get_api_manager():
    """获取API管理器实例"""
    global api_manager
    if api_manager is None:
        api_manager = APIManager()
    return api_manager
