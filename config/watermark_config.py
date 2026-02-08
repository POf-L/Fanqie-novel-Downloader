# -*- coding: utf-8 -*-
"""
水印配置文件
集中管理水印相关的配置参数，提高可维护性和灵活性
"""

# 水印插入配置
WATERMARK_CONFIG = {
    'INSERT_INTERVAL': 50000,  # 水印插入间隔（字符数）
    'POSITION_VARIATION': 0.2,  # 插入位置变化范围（20%）
    'MIN_INVISIBLE_CHARS': 3,   # 最小隐形字符数量
    'MAX_INVISIBLE_CHARS': 8,   # 最大隐形字符数量
}

# 网络请求配置
NETWORK_CONFIG = {
    'TIMEOUT': 10,           # 请求超时时间（秒）
    'MAX_RETRIES': 3,        # 最大重试次数
    'BASE_DELAY': 1,         # 基础延迟时间（秒）
    'API_LIMIT_DELAY': 5,    # API限制时的额外延迟（秒）
    'USER_AGENT': 'Fanqie-novel-Downloader/1.0'  # 用户代理
}

# 仓库配置
REPO_CONFIG = {
    'DEFAULT_REPO': "POf-L/Fanqie-novel-Downloader",  # 默认仓库
    'MAX_REPO_LENGTH': 100,  # 仓库名称最大长度
    'MIN_REPO_LENGTH': 3,    # 仓库名称最小长度
}

# 安全配置
SECURITY_CONFIG = {
    'DANGEROUS_CHARS': [';', '&', '|', '`', '$', '(', ')', '<', '>', '"', "'", '\\'],  # 危险字符列表
    'ENABLE_SECURITY_CHECK': True,  # 是否启用安全检查
}
