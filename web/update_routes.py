# -*- coding: utf-8 -*-
"""
更新相关路由 - 从 web_app.py 拆分，避免单文件过长
"""

from __future__ import annotations

import json
import os
import threading
from typing import Callable

from flask import jsonify, request


def init_update_routes(
    app,
    *,
    config_file: str,
    get_default_download_path: Callable[[], str],
    update_download_worker: Callable[[str, str, str], None],
    get_update_download_status: Callable[[], dict],
):
    @app.route('/api/check-update', methods=['GET'])
    def api_check_update():
        """检查更新"""
        try:
            import sys
            from utils.updater import check_and_notify, parse_release_assets, get_current_platform
            from config.config import __version__, __github_repo__

            if not getattr(sys, 'frozen', False):
                return jsonify({
                    'success': True,
                    'has_update': False,
                    'is_source': True,
                    'message': '源代码运行模式，不检查更新'
                })

            update_info = check_and_notify(__version__, __github_repo__, silent=True)

            if update_info:
                has_update = update_info.get('has_update', False)
                
                if has_update and update_info.get('release_info'):
                    platform = get_current_platform()
                    assets = parse_release_assets(update_info['release_info'], platform)
                    
                    if assets:
                        recommended_asset = assets[0]
                        update_info['download_url'] = recommended_asset['download_url']
                        update_info['filename'] = recommended_asset['name']
                
                return jsonify({
                    'success': True,
                    'has_update': has_update,
                    'data': update_info
                })
            else:
                return jsonify({
                    'success': True,
                    'has_update': False
                })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/download-update', methods=['POST'])
    def api_download_update():
        """开始下载更新包"""
        data = request.get_json() or {}
        url = data.get('url')
        filename = data.get('filename')

        if not url or not filename:
            return jsonify({'success': False, 'message': '参数错误'}), 400

        # 使用默认下载路径或配置路径
        save_path = get_default_download_path()
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    save_path = config.get('save_path', save_path)
            except Exception:
                pass

        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except Exception:
                save_path = get_default_download_path()

        # 启动下载线程
        t = threading.Thread(
            target=update_download_worker,
            args=(url, save_path, filename),
            daemon=True
        )
        t.start()

        return jsonify({'success': True, 'message': '开始下载'})

    @app.route('/api/update-status', methods=['GET'])
    def api_get_update_status_route():
        """获取更新下载状态"""
        return jsonify(get_update_download_status())

    @app.route('/api/can-auto-update', methods=['GET'])
    def api_can_auto_update():
        """检查是否支持自动更新"""
        try:
            from utils.updater import can_auto_update
            return jsonify({
                'success': True,
                'can_auto_update': can_auto_update()
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/apply-update', methods=['POST'])
    def api_apply_update():
        """应用已下载的更新（支持 Windows/Linux/macOS）"""
        try:
            from utils.updater import apply_update, can_auto_update
            import sys

            print(f'[DEBUG] sys.frozen: {getattr(sys, "frozen", False)}')
            print(f'[DEBUG] sys.executable: {sys.executable}')

            can_update = can_auto_update()
            print(f'[DEBUG] can_auto_update: {can_update}')
            if not can_update:
                return jsonify({
                    'success': False,
                    'message': '当前平台不支持自动更新'
                }), 400

            # 获取下载的更新文件信息
            status = get_update_download_status()
            print(f'[DEBUG] update_status: {status}')
            if not status.get('completed'):
                return jsonify({
                    'success': False,
                    'message': '更新文件未下载完成'
                }), 400

            new_file_path = status.get('temp_file_path', '')
            print(f'[DEBUG] temp_file_path: {new_file_path}')

            if not new_file_path:
                return jsonify({
                    'success': False,
                    'message': '更新文件信息不完整'
                }), 400

            print(f'[DEBUG] file exists: {os.path.exists(new_file_path)}')

            if not os.path.exists(new_file_path):
                return jsonify({
                    'success': False,
                    'message': f'更新文件不存在: {new_file_path}'
                }), 400

            print(f'[DEBUG] file size: {os.path.getsize(new_file_path)} bytes')

            # 应用更新（自动检测平台）
            print('[DEBUG] Calling apply_update...')
            if apply_update(new_file_path):
                # 更新成功启动，准备退出程序
                def delayed_exit():
                    import time
                    print('[DEBUG] Waiting for update script to start...')
                    time.sleep(3)
                    print('[DEBUG] Exiting application for update...')
                    os._exit(0)

                # 使用非守护线程确保退出逻辑能完成
                exit_thread = threading.Thread(target=delayed_exit, daemon=False)
                exit_thread.start()

                return jsonify({
                    'success': True,
                    'message': '更新已启动'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '更新启动失败'
                }), 500

        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

