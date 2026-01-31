# -*- coding: utf-8 -*-
"""配置相关API路由"""

from flask import Blueprint, request, jsonify
import os
import sys
import json
import subprocess

from .shared_state import (
    get_default_download_path, CONFIG_FILE,
    _read_local_config, _write_local_config
)

config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config/save-path', methods=['GET', 'POST'])
def api_config_save_path():
    """获取/保存下载路径配置"""
    
    if request.method == 'GET':
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return jsonify({'path': config.get('save_path', get_default_download_path())})
        except:
            pass
        return jsonify({'path': get_default_download_path()})
    
    else:
        data = request.get_json()
        path = data.get('path', get_default_download_path())
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            config['save_path'] = path
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


@config_bp.route('/api/list-directory', methods=['POST'])
def api_list_directory():
    """列出指定目录的内容"""
    try:
        data = request.get_json() or {}
        path = data.get('path', '')
        
        if not path:
            path = get_default_download_path()
        
        path = os.path.normpath(os.path.expanduser(path))
        
        if not os.path.exists(path):
            return jsonify({
                'success': False,
                'message': '目录不存在'
            })
        
        if not os.path.isdir(path):
            return jsonify({
                'success': False,
                'message': '路径不是目录'
            })
        
        directories = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                directories.append({
                    'name': item,
                    'path': item_path
                })
        
        directories.sort(key=lambda x: x['name'].lower())
        
        parent_path = os.path.dirname(path)
        is_root = (parent_path == path) or (path in ['/', '\\'])
        
        drives = []
        if os.name == 'nt':
            import string
            for letter in string.ascii_uppercase:
                drive = f'{letter}:\\'
                if os.path.exists(drive):
                    drives.append({
                        'name': f'{letter}:',
                        'path': drive
                    })
        
        quick_paths = []
        
        # 获取程序所在目录
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 添加程序目录下的novels文件夹作为第一个快捷路径
        novels_dir = os.path.join(base_dir, 'novels')
        if os.path.exists(novels_dir) or True:  # 即使不存在也显示
            quick_paths.append({
                'name': '默认下载目录',
                'path': novels_dir,
                'icon': 'line-md:folder'
            })
        
        home = os.path.expanduser('~')
        
        if os.name == 'nt':
            shell_folders = [
                ('Desktop', 'Desktop', 'line-md:computer'),
                ('Downloads', 'Downloads', 'line-md:download-loop'),
                ('Documents', 'Documents', 'line-md:document'),
                ('Pictures', 'Pictures', 'line-md:image'),
                ('Music', 'Music', 'line-md:play'),
                ('Videos', 'Videos', 'line-md:play-filled'),
            ]
            for name, folder, icon in shell_folders:
                folder_path = os.path.join(home, folder)
                if os.path.exists(folder_path):
                    quick_paths.append({
                        'name': name,
                        'path': folder_path,
                        'icon': icon
                    })
        else:
            unix_folders = [
                ('Desktop', 'Desktop', 'line-md:computer'),
                ('Downloads', 'Downloads', 'line-md:download-loop'),
                ('Documents', 'Documents', 'line-md:document'),
                ('Pictures', 'Pictures', 'line-md:image'),
                ('Music', 'Music', 'line-md:play'),
                ('Videos', 'Videos', 'line-md:play-filled'),
            ]
            for name, folder, icon in unix_folders:
                folder_path = os.path.join(home, folder)
                if os.path.exists(folder_path):
                    quick_paths.append({
                        'name': name,
                        'path': folder_path,
                        'icon': icon
                    })
        
        return jsonify({
            'success': True,
            'data': {
                'current_path': path,
                'parent_path': parent_path if not is_root else None,
                'directories': directories,
                'is_root': is_root,
                'drives': drives if os.name == 'nt' else None,
                'quick_paths': quick_paths
            }
        })
    except PermissionError:
        return jsonify({
            'success': False,
            'message': '无权限访问该目录'
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] list-directory: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'加载目录失败: {str(e)}'
        })


@config_bp.route('/api/select-folder', methods=['POST'])
def api_select_folder():
    """保存选择的文件夹路径"""
    data = request.get_json() or {}
    selected_path = data.get('path', '')
    
    if not selected_path:
        return jsonify({'success': False, 'message': '未选择文件夹'})
    
    if not os.path.exists(selected_path) or not os.path.isdir(selected_path):
        return jsonify({'success': False, 'message': '无效的目录路径'})
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        config['save_path'] = selected_path
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'path': selected_path})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@config_bp.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    """打开文件夹"""
    data = request.get_json()
    path = data.get('path')

    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'message': '路径不存在'}), 400

    try:
        if os.name == 'nt':
            os.startfile(path)
        elif os.name == 'posix':
            subprocess.call(['open', path])
        else:
            subprocess.call(['xdg-open', path])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@config_bp.route('/api/settings/get', methods=['GET'])
def api_get_settings():
    """获取用户设置"""
    try:
        settings = _read_local_config()
        if not settings or 'user_settings' not in settings:
            default_settings = {
                'max_workers': 30,
                'request_rate_limit': 0.02,
                'connection_pool_size': 200,
                'async_batch_size': 50,
                'max_retries': 3,
                'request_timeout': 30,
                'api_rate_limit': 50,
                'rate_limit_window': 1.0
            }
            return jsonify({'success': True, 'settings': default_settings})

        return jsonify({'success': True, 'settings': settings.get('user_settings', {})})
    except Exception as e:
        print(f"[ERROR] get-settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@config_bp.route('/api/settings/save', methods=['POST'])
def api_save_settings():
    """保存用户设置"""
    try:
        data = request.get_json()
        settings = data.get('settings', {})

        if not settings:
            return jsonify({'success': False, 'error': '无效的设置数据'}), 400

        validation_errors = []

        if 'max_workers' in settings:
            value = settings['max_workers']
            if not isinstance(value, (int, float)) or value < 1 or value > 100:
                validation_errors.append('最大并发数必须在1-100之间')

        if 'request_rate_limit' in settings:
            value = settings['request_rate_limit']
            if not isinstance(value, (int, float)) or value < 0 or value > 10:
                validation_errors.append('请求间隔必须在0-10秒之间')

        if 'connection_pool_size' in settings:
            value = settings['connection_pool_size']
            if not isinstance(value, (int, float)) or value < 10 or value > 500:
                validation_errors.append('连接池大小必须在10-500之间')

        if 'async_batch_size' in settings:
            value = settings['async_batch_size']
            if not isinstance(value, (int, float)) or value < 1 or value > 200:
                validation_errors.append('异步批次大小必须在1-200之间')

        if 'max_retries' in settings:
            value = settings['max_retries']
            if not isinstance(value, (int, float)) or value < 0 or value > 10:
                validation_errors.append('最大重试次数必须在0-10之间')

        if 'request_timeout' in settings:
            value = settings['request_timeout']
            if not isinstance(value, (int, float)) or value < 5 or value > 300:
                validation_errors.append('请求超时必须在5-300秒之间')

        if 'api_rate_limit' in settings:
            value = settings['api_rate_limit']
            if not isinstance(value, (int, float)) or value < 1 or value > 200:
                validation_errors.append('API速率限制必须在1-200之间')

        if 'rate_limit_window' in settings:
            value = settings['rate_limit_window']
            if not isinstance(value, (int, float)) or value < 0.1 or value > 10:
                validation_errors.append('速率窗口必须在0.1-10秒之间')

        if validation_errors:
            return jsonify({'success': False, 'error': '; '.join(validation_errors)}), 400

        success = _write_local_config({'user_settings': settings})

        if success:
            return jsonify({'success': True, 'message': '设置已保存'})
        else:
            return jsonify({'success': False, 'error': '保存设置失败'}), 500

    except Exception as e:
        print(f"[ERROR] save-settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
