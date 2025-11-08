#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试脚本 - 测试小说ID 6982529841564224526 的完整功能
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from novel_downloader import get_api_manager

def test_novel_functions():
    """综合测试小说相关功能"""
    book_id = "6982529841564224526"
    
    print(f"正在综合测试小说ID: {book_id} 的所有功能...")
    
    # 获取API管理器
    api_manager = get_api_manager()
    if api_manager is None:
        print("❌ API管理器初始化失败")
        return False
    
    print("✅ API管理器初始化成功")
    
    results = {}
    
    # 测试1: 获取书籍信息
    print("\n" + "-" * 30)
    print("测试1: 获取书籍信息")
    print("-" * 30)
    try:
        book_info = api_manager.get_book_info(book_id)
        if book_info:
            results['book_info'] = {
                'status': 'success',
                'data': {
                    'book_name': book_info.get('book_name', '未知'),
                    'author': book_info.get('author', '未知'),
                    'intro': book_info.get('intro', '无'),
                    'cover': book_info.get('cover', '无')
                }
            }
            print(f"✅ 书名: {book_info.get('book_name', '未知')}")
            print(f"✅ 作者: {book_info.get('author', '未知')}")
        else:
            results['book_info'] = {'status': 'failed'}
            print("❌ 获取书籍信息失败")
    except Exception as e:
        results['book_info'] = {'status': 'error', 'error': str(e)}
        print(f"❌ 获取书籍信息异常: {str(e)}")
    
    # 测试2: 获取章节列表
    print("\n" + "-" * 30)
    print("测试2: 获取章节列表")
    print("-" * 30)
    try:
        chapters = api_manager.get_chapter_list(book_id)
        if chapters:
            results['chapter_list'] = {
                'status': 'success',
                'count': len(chapters),
                'first_chapter': chapters[0] if chapters else None,
                'last_chapter': chapters[-1] if chapters else None
            }
            print(f"✅ 成功获取 {len(chapters)} 章")
            print(f"✅ 第一章: {chapters[0].get('chapter_name', '未知')}")
            print(f"✅ 最后一章: {chapters[-1].get('chapter_name', '未知')}")
        else:
            results['chapter_list'] = {'status': 'failed'}
            print("❌ 获取章节列表失败")
    except Exception as e:
        results['chapter_list'] = {'status': 'error', 'error': str(e)}
        print(f"❌ 获取章节列表异常: {str(e)}")
    
    # 测试3: 获取章节内容
    print("\n" + "-" * 30)
    print("测试3: 获取章节内容")
    print("-" * 30)
    try:
        if results.get('chapter_list', {}).get('status') == 'success':
            first_chapter_id = results['chapter_list']['first_chapter']['chapter_id']
            content_data = api_manager.get_chapter_content(first_chapter_id)
            if content_data:
                content = content_data.get('content', '')
                results['chapter_content'] = {
                    'status': 'success',
                    'content_length': len(content),
                    'title': content_data.get('title', ''),
                    'preview': content[:100] + '...' if len(content) > 100 else content
                }
                print(f"✅ 成功获取章节内容，共 {len(content)} 个字符")
                print(f"✅ 内容预览: {content[:100]}...")
            else:
                results['chapter_content'] = {'status': 'failed'}
                print("❌ 获取章节内容失败")
        else:
            results['chapter_content'] = {'status': 'skipped', 'reason': 'chapter_list_failed'}
            print("⚠️ 跳过章节内容测试（章节列表获取失败）")
    except Exception as e:
        results['chapter_content'] = {'status': 'error', 'error': str(e)}
        print(f"❌ 获取章节内容异常: {str(e)}")
    
    # 测试4: API连接测试
    print("\n" + "-" * 30)
    print("测试4: API连接测试")
    print("-" * 30)
    try:
        connection_ok = api_manager.test_connection()
        results['api_connection'] = {
            'status': 'success' if connection_ok else 'failed'
        }
        if connection_ok:
            print("✅ API连接正常")
        else:
            print("❌ API连接失败")
    except Exception as e:
        results['api_connection'] = {'status': 'error', 'error': str(e)}
        print(f"❌ API连接测试异常: {str(e)}")
    
    return results

def generate_report(results):
    """生成测试报告"""
    print("\n" + "=" * 50)
    print("测试报告")
    print("=" * 50)
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.get('status') == 'success')
    
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    print("\n详细结果:")
    for test_name, result in results.items():
        status = result.get('status', 'unknown')
        status_icon = {
            'success': '✅',
            'failed': '❌',
            'error': '💥',
            'skipped': '⚠️'
        }.get(status, '❓')
        
        test_display_name = {
            'book_info': '书籍信息获取',
            'chapter_list': '章节列表获取',
            'chapter_content': '章节内容获取',
            'api_connection': 'API连接测试'
        }.get(test_name, test_name)
        
        print(f"  {status_icon} {test_display_name}: {status}")
        if status == 'error':
            print(f"    错误: {result.get('error', '未知错误')}")
        elif status == 'skipped':
            print(f"    原因: {result.get('reason', '未知原因')}")
    
    # 保存详细报告到文件
    try:
        with open('test_report.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n📄 详细报告已保存到: test_report.json")
    except Exception as e:
        print(f"\n⚠️ 保存报告失败: {str(e)}")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    print("=" * 50)
    print("番茄小说下载器 - 综合功能测试")
    print(f"测试小说ID: 6982529841564224526")
    print("=" * 50)
    
    results = test_novel_functions()
    all_passed = generate_report(results)
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有测试通过！项目功能完全正常")
        print("✅ 项目能够成功获取小说6982529841564224526的目录和内容")
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
    print("=" * 50)
