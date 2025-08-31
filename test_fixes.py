#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复脚本
验证更新系统和EPUB封面的修复
"""

import os
import sys
import tempfile
import json
from pathlib import Path

def test_epub_cover():
    """测试EPUB封面功能"""
    print("=== 测试EPUB封面功能 ===")
    
    try:
        # 测试封面下载和处理
        from novel_downloader import download_and_process_cover, create_default_cover
        from config import get_headers
        
        print("1. 测试默认封面生成...")
        default_cover = create_default_cover("测试小说", "测试作者")
        if default_cover:
            print(f"✓ 默认封面生成成功，大小: {len(default_cover)} 字节")
        else:
            print("✗ 默认封面生成失败")
        
        print("2. 测试封面下载处理...")
        # 使用一个测试图片URL
        test_url = "https://via.placeholder.com/400x600/FF0000/FFFFFF?text=Test"
        headers = get_headers()
        content, ext, mime = download_and_process_cover(test_url, headers)
        if content and ext and mime:
            print(f"✓ 封面下载成功: {ext}, {mime}, {len(content)} 字节")
        else:
            print("✗ 封面下载失败")
            
    except ImportError as e:
        print(f"✗ 导入模块失败: {e}")
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")

def test_updater():
    """测试更新系统"""
    print("\n=== 测试更新系统 ===")
    
    try:
        from updater import UpdateChecker, AutoUpdater
        
        print("1. 测试更新检查器...")
        checker = UpdateChecker("test/repo", "1.0.0")
        print(f"✓ 更新检查器创建成功: {checker.github_repo}")
        
        print("2. 测试自动更新器...")
        updater = AutoUpdater("test/repo", "1.0.0")
        print(f"✓ 自动更新器创建成功: {updater.github_repo}")
        
        print("3. 测试日志功能...")
        updater._create_update_log("测试日志消息")
        print("✓ 日志功能正常")
        
    except ImportError as e:
        print(f"✗ 导入模块失败: {e}")
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")

def test_external_updater():
    """测试外部更新脚本"""
    print("\n=== 测试外部更新脚本 ===")
    
    try:
        from external_updater import log_message, get_current_exe_path
        
        print("1. 测试日志功能...")
        log_message("测试外部更新脚本日志")
        print("✓ 日志功能正常")
        
        print("2. 测试可执行文件路径获取...")
        exe_path = get_current_exe_path()
        print(f"✓ 可执行文件路径: {exe_path}")
        
    except ImportError as e:
        print(f"✗ 导入模块失败: {e}")
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")

def test_epub_creation():
    """测试EPUB创建"""
    print("\n=== 测试EPUB创建 ===")
    
    try:
        from ebooklib import epub
        
        print("1. 测试EPUB基础功能...")
        book = epub.EpubBook()
        book.set_title("测试小说")
        book.set_language('zh-CN')
        book.add_author("测试作者")
        
        print("✓ EPUB基础功能正常")
        
        print("2. 测试封面设置...")
        # 创建一个简单的测试封面
        test_cover = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # 简单的PNG头
        
        cover_item = epub.EpubItem(
            uid='cover-image',
            file_name='cover.png',
            media_type='image/png',
            content=test_cover
        )
        book.add_item(cover_item)
        book.set_cover('cover.png', test_cover)
        book.add_metadata('DC', 'relation', 'cover-image')
        book.add_metadata('OPF', 'cover', 'cover-image')
        
        print("✓ 封面设置功能正常")
        
        # 测试保存
        temp_dir = tempfile.gettempdir()
        test_file = os.path.join(temp_dir, 'test_epub.epub')
        
        epub.write_epub(test_file, book, {})
        if os.path.exists(test_file):
            print(f"✓ EPUB文件创建成功: {test_file}")
            # 清理测试文件
            os.remove(test_file)
            print("✓ 测试文件已清理")
        else:
            print("✗ EPUB文件创建失败")
            
    except ImportError as e:
        print(f"✗ 导入模块失败: {e}")
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")

def main():
    """主测试函数"""
    print("开始测试修复内容...")
    print("=" * 50)
    
    # 运行各项测试
    test_epub_cover()
    test_updater()
    test_external_updater()
    test_epub_creation()
    
    print("\n" + "=" * 50)
    print("测试完成！")
    
    # 检查是否有错误
    print("\n建议:")
    print("1. 如果所有测试都通过，说明修复成功")
    print("2. 如果有测试失败，请检查相关模块的导入和依赖")
    print("3. 建议在实际环境中测试更新和EPUB生成功能")

if __name__ == "__main__":
    main()