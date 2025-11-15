#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
编译配置脚本 - 为 PyInstaller 生成必要的配置
"""

import os
import sys
import argparse
from pathlib import Path

def create_pyinstaller_config(output_dir="."):
    """创建 PyInstaller 配置"""
    
    config_content = '''
# PyInstaller 配置 - HTML5 Web 版本
# 自动为 Flask + PyWebView 应用配置隐藏导入和数据文件

HIDDEN_IMPORTS = [
    'flask',
    'flask_cors',
    'pywebview',
    'PIL',
    'requests',
    'aiohttp',
    'beautifulsoup4',
    'ebooklib',
    'fake_useragent',
]

DATA_FILES = [
    ('static', 'static'),
    ('templates', 'templates'),
]
'''
    
    config_path = Path(output_dir) / "pyinstaller_config.py"
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"✅ PyInstaller 配置已创建: {config_path}")

def verify_build_requirements():
    """验证编译所需的依赖"""
    
    required_packages = [
        'pyinstaller',
        'flask',
        'flask_cors',
        'pywebview',
        'PIL',
    ]
    
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} 已安装")
        except ImportError:
            missing.append(package)
            print(f"❌ {package} 未安装")
    
    if missing:
        print(f"\n需要安装: {' '.join(missing)}")
        print(f"运行: pip install {' '.join(missing)}")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description="编译配置工具")
    parser.add_argument("--init", action="store_true", help="初始化编译配置")
    parser.add_argument("--verify", action="store_true", help="验证编译依赖")
    
    args = parser.parse_args()
    
    if args.init:
        create_pyinstaller_config()
    
    if args.verify:
        if verify_build_requirements():
            print("\n✅ 所有依赖已满足，可以开始编译")
        else:
            print("\n❌ 有缺失的依赖，请先安装")
            sys.exit(1)
    
    if not args.init and not args.verify:
        parser.print_help()

if __name__ == "__main__":
    main()
