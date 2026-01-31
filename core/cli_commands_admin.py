# -*- coding: utf-8 -*-
"""
CLI 子命令实现（状态/配置/API）- 从 core/cli.py 拆分
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.cli_utils import format_table
from utils.platform_utils import detect_platform, get_feature_status_report

def cmd_status(args):
    """显示平台状态命令"""
    report = get_feature_status_report()
    print(report)
    return 0


def cmd_config(args):
    """配置管理命令"""
    from config.config import CONFIG
    import sys

    # 获取配置文件路径
    if getattr(sys, 'frozen', False):
        # 打包环境
        if hasattr(sys, '_MEIPASS'):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 创建 config 目录
    config_dir = os.path.join(base_dir, 'config')
    os.makedirs(config_dir, exist_ok=True)
    config_file = os.path.join(config_dir, 'fanqie_novel_downloader_config.json')

    # 读取本地配置
    def read_config():
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    # 写入本地配置
    def write_config(updates):
        try:
            cfg = read_config()
            cfg.update(updates)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    # 列出所有配置
    if args.action == 'list':
        cfg = read_config()
        print("\n当前配置:")
        print("=" * 50)

        # API 节点配置
        api_mode = cfg.get('api_base_url_mode', 'auto')
        api_url = cfg.get('api_base_url', '')
        print(f"API 节点模式: {api_mode}")
        if api_url:
            print(f"API 节点 URL: {api_url}")

        # 下载参数配置
        if 'max_workers' in cfg:
            print(f"最大并发数: {cfg['max_workers']}")
        if 'api_rate_limit' in cfg:
            print(f"API 速率限制: {cfg['api_rate_limit']}")
        if 'request_rate_limit' in cfg:
            print(f"请求速率限制: {cfg['request_rate_limit']}")
        if 'connection_pool_size' in cfg:
            print(f"连接池大小: {cfg['connection_pool_size']}")

        # 水印配置
        if 'watermark_enabled' in cfg:
            print(f"水印开关: {'开启' if cfg['watermark_enabled'] else '关闭'}")

        # 语言配置
        if 'language' in cfg:
            print(f"界面语言: {cfg['language']}")

        # 保存路径
        if 'save_path' in cfg:
            print(f"默认保存路径: {cfg['save_path']}")

        print("=" * 50)
        return 0

    # 设置配置项
    elif args.action == 'set':
        if not args.key or args.value is None:
            print("错误: 请提供配置键和值")
            print("用法: config set <key> <value>")
            return 1

        # 验证和转换配置值
        key = args.key
        value = args.value

        # 数值类型配置
        if key in ['max_workers', 'api_rate_limit', 'request_rate_limit', 'connection_pool_size']:
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                print(f"错误: {key} 必须是数值")
                return 1

        # 布尔类型配置
        elif key in ['watermark_enabled']:
            value = value.lower() in ['true', '1', 'yes', 'on', '开启']

        # 字符串类型配置
        elif key in ['api_base_url', 'api_base_url_mode', 'language', 'save_path']:
            value = str(value)

        else:
            print(f"警告: 未知的配置项 '{key}'，将按字符串保存")

        # 保存配置
        if write_config({key: value}):
            print(f"✓ 配置已保存: {key} = {value}")
            return 0
        else:
            return 1

    # 获取配置项
    elif args.action == 'get':
        if not args.key:
            print("错误: 请提供配置键")
            print("用法: config get <key>")
            return 1

        cfg = read_config()
        if args.key in cfg:
            print(f"{args.key} = {cfg[args.key]}")
            return 0
        else:
            print(f"配置项 '{args.key}' 不存在")
            return 1

    # 重置配置
    elif args.action == 'reset':
        if args.key:
            # 重置单个配置项
            cfg = read_config()
            if args.key in cfg:
                del cfg[args.key]
                try:
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                    print(f"✓ 已重置配置: {args.key}")
                    return 0
                except Exception as e:
                    print(f"重置配置失败: {e}")
                    return 1
            else:
                print(f"配置项 '{args.key}' 不存在")
                return 1
        else:
            # 重置所有配置
            try:
                if os.path.exists(config_file):
                    os.remove(config_file)
                print("✓ 已重置所有配置")
                return 0
            except Exception as e:
                print(f"重置配置失败: {e}")
                return 1

    else:
        print(f"错误: 未知的操作 '{args.action}'")
        return 1


def cmd_api(args):
    """API 节点管理命令"""
    from config.config import CONFIG
    import sys
    import requests
    import time

    # 获取配置文件路径
    if getattr(sys, 'frozen', False):
        # 打包环境
        if hasattr(sys, '_MEIPASS'):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 创建 config 目录
    config_dir = os.path.join(base_dir, 'config')
    os.makedirs(config_dir, exist_ok=True)
    config_file = os.path.join(config_dir, 'fanqie_novel_downloader_config.json')

    # 读取本地配置
    def read_config():
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    # 写入本地配置
    def write_config(updates):
        try:
            cfg = read_config()
            cfg.update(updates)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    # 探测 API 节点
    def probe_api_source(base_url, timeout=2.0):
        """探测 API 节点的可用性和延迟"""
        base_url = base_url.strip().rstrip('/')
        test_url = f"{base_url}/api/health"

        try:
            start = time.time()
            response = requests.get(test_url, timeout=timeout, verify=False)
            latency_ms = int((time.time() - start) * 1000)

            available = response.status_code == 200
            return {
                'base_url': base_url,
                'available': available,
                'latency_ms': latency_ms,
                'status_code': response.status_code
            }
        except requests.exceptions.Timeout:
            return {
                'base_url': base_url,
                'available': False,
                'latency_ms': None,
                'error': '超时'
            }
        except Exception as e:
            return {
                'base_url': base_url,
                'available': False,
                'latency_ms': None,
                'error': str(e)[:50]
            }

    # 列出所有 API 节点
    if args.action == 'list':
        api_sources = CONFIG.get('api_sources', [])
        current_url = CONFIG.get('api_base_url', '')

        print("\n可用的 API 节点:")
        print("=" * 70)

        # 并发探测所有节点
        print("正在探测节点可用性...\n")

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for source in api_sources:
                if isinstance(source, dict):
                    base_url = source.get('base_url', '')
                else:
                    base_url = str(source)

                if base_url:
                    futures.append(executor.submit(probe_api_source, base_url))

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"探测失败: {e}")

        # 按可用性和延迟排序
        results.sort(key=lambda x: (
            not x.get('available'),
            x.get('latency_ms') or 999999
        ))

        # 显示结果表格
        headers = ['序号', 'URL', '状态', '延迟 (ms)', '当前']
        rows = []
        for i, result in enumerate(results, 1):
            url = result['base_url']
            available = result.get('available', False)
            latency = result.get('latency_ms')
            error = result.get('error', '')

            status = "✓ 可用" if available else f"✗ 不可用"
            if error:
                status += f" ({error})"

            latency_str = str(latency) if latency else "-"
            is_current = "★" if url == current_url else ""

            rows.append([i, url[:40], status, latency_str, is_current])

        print(format_table(headers, rows))
        print("=" * 70)

        cfg = read_config()
        mode = cfg.get('api_base_url_mode', 'auto')
        print(f"\n当前模式: {mode}")
        if current_url:
            print(f"当前节点: {current_url}")
        print()

        return 0

    # 选择 API 节点
    elif args.action == 'select':
        if args.mode == 'auto':
            # 自动选择最快的可用节点
            api_sources = CONFIG.get('api_sources', [])
            print("正在探测节点可用性...")

            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for source in api_sources:
                    if isinstance(source, dict):
                        base_url = source.get('base_url', '')
                    else:
                        base_url = str(source)

                    if base_url:
                        futures.append(executor.submit(probe_api_source, base_url))

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception:
                        pass

            # 选择最快的可用节点
            available = [r for r in results if r.get('available')]
            if not available:
                print("错误: 没有可用的 API 节点")
                return 1

            available.sort(key=lambda x: x.get('latency_ms') or 999999)
            best = available[0]

            if write_config({'api_base_url_mode': 'auto', 'api_base_url': best['base_url']}):
                print(f"✓ 已选择最快节点: {best['base_url']} (延迟: {best['latency_ms']}ms)")
                return 0
            else:
                return 1

        elif args.mode == 'manual':
            if not args.url:
                print("错误: 请提供 API 节点 URL")
                print("用法: api select manual <url>")
                return 1

            # 探测指定节点
            result = probe_api_source(args.url)
            if not result.get('available'):
                error = result.get('error', '不可用')
                print(f"错误: 节点不可用: {args.url} ({error})")
                return 1

            if write_config({'api_base_url_mode': 'manual', 'api_base_url': args.url}):
                print(f"✓ 已选择节点: {args.url} (延迟: {result['latency_ms']}ms)")
                return 0
            else:
                return 1

        else:
            print(f"错误: 未知的模式 '{args.mode}'")
            return 1

    else:
        print(f"错误: 未知的操作 '{args.action}'")
        return 1
