# -*- coding: utf-8 -*-
"""
Web应用程序 - Flask后端，用于HTML GUI（简化版 - 导入模块化组件）
"""

import os
import sys
import json
import threading

# 添加父目录到路径以便导入其他模块（打包环境和开发环境都需要）
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        _base_path = sys._MEIPASS
    else:
        _base_path = os.path.dirname(sys.executable)
    if _base_path not in sys.path:
        sys.path.insert(0, _base_path)
else:
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging

from config.config import __version__ as APP_VERSION
from config.config import CONFIG, ConfigLoadError, _LOCAL_CONFIG_FILE

# 禁用Flask默认日志
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# 获取模板和静态文件路径（支持打包环境）
def _get_web_paths():
    """获取模板和静态文件的绝对路径，支持打包环境"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(sys.executable)
        template_folder = os.path.join(base_path, 'templates')
        static_folder = os.path.join(base_path, 'static')
    else:
        template_folder = os.path.join(os.path.dirname(__file__), 'templates')
        static_folder = os.path.join(os.path.dirname(__file__), 'static')
    return template_folder, static_folder

_template_folder, _static_folder = _get_web_paths()
app = Flask(__name__, template_folder=_template_folder, static_folder=_static_folder)
CORS(app)

# 访问令牌（由main.py在启动时设置）
ACCESS_TOKEN = None

# 节点探测结果缓存（启动时探测，下载时复用）
PROBED_NODES_CACHE = {}

def set_access_token(token):
    """设置访问令牌"""
    global ACCESS_TOKEN
    ACCESS_TOKEN = token

def get_available_nodes() -> list:
    """获取可用节点列表（已探测通过的节点）"""
    return [url for url, info in PROBED_NODES_CACHE.items() if info.get('available')]

def get_full_download_nodes() -> list:
    """获取支持整本下载的可用节点列表"""
    return [url for url, info in PROBED_NODES_CACHE.items()
            if info.get('available') and info.get('supports_full_download')]

def is_node_available(base_url: str) -> bool:
    """检查节点是否可用"""
    base_url = _normalize_base_url(base_url)
    if base_url in PROBED_NODES_CACHE:
        return PROBED_NODES_CACHE[base_url].get('available', False)
    return True

def update_probed_cache(probed_results: list):
    """更新节点探测缓存"""
    global PROBED_NODES_CACHE
    for result in probed_results:
        base_url = _normalize_base_url(result.get('base_url', ''))
        if base_url:
            PROBED_NODES_CACHE[base_url] = {
                'available': result.get('available', False),
                'latency_ms': result.get('latency_ms'),
                'supports_full_download': result.get('supports_full_download', True),
                'error': result.get('error')
            }

def _normalize_base_url(url: str) -> str:
    return (url or '').strip().rstrip('/')

def get_config_dir():
    """获取配置文件目录"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    config_dir = os.path.join(base_dir, 'config')
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

CONFIG_FILE = _LOCAL_CONFIG_FILE

def _read_local_config() -> dict:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def _write_local_config(updates: dict) -> bool:
    try:
        cfg = _read_local_config()
        cfg.update(updates or {})
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def get_default_download_path():
    """获取默认下载路径（程序所在目录的novels文件夹）"""
    # 获取程序所在目录
    if getattr(sys, 'frozen', False):
        # 打包环境
        if hasattr(sys, '_MEIPASS'):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    else:
        # 开发环境 - 使用项目根目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 默认下载到程序目录下的novels文件夹
    downloads = os.path.join(base_dir, 'novels')
    
    if not os.path.exists(downloads):
        try:
            os.makedirs(downloads, exist_ok=True)
        except:
            # 如果创建失败，使用程序根目录
            downloads = base_dir
    
    return downloads

# ===================== 导入模块化组件 =====================

# 导入下载工作线程
from .download_worker import get_status, update_status, download_thread

# 导入API源管理器
from .api_source_manager import (
    _get_api_sources, _get_ip_location, _format_location_name,
    _probe_api_source, _apply_api_base_url, _ensure_api_base_url
)

# 导入任务管理器
from .task_manager import task_manager

# 导入更新下载器
from .update_downloader import get_update_status as get_update_download_status, update_download_worker

# 导入API路由
from .api_routes import init_routes

# 初始化路由
init_routes(app)

# ===================== 访问控制中间件 =====================

@app.before_request
def check_access():
    """请求前验证访问令牌"""
    # 静态文件不需要验证
    if request.path.startswith('/static/'):
        return None
    
    # 验证token
    if ACCESS_TOKEN is not None:
        token = request.args.get('token') or request.headers.get('X-Access-Token')
        if token != ACCESS_TOKEN:
            return jsonify({'error': 'Forbidden'}), 403
    
    return None

# ===================== 主路由 =====================

@app.route('/')
def index():
    """主页"""
    token = request.args.get('token', '')
    return render_template('index.html', version=APP_VERSION, access_token=token)

@app.route('/api/init', methods=['POST'])
def api_init():
    """初始化模块"""
    try:
        from core.novel_downloader import init_modules
        if init_modules(skip_api_select=True):
            return jsonify({'success': True, 'message': '模块加载成功'})
        return jsonify({'success': False, 'message': '模块加载失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/version', methods=['GET'])
def api_version():
    """获取当前版本号"""
    return jsonify({'success': True, 'version': APP_VERSION})

@app.route('/api/status', methods=['GET'])
def api_status():
    """获取下载状态"""
    return jsonify(get_status())

@app.route('/api/health', methods=['GET'])
def api_health():
    """健康检查 API"""
    return jsonify({'status': 'ready', 'success': True})

@app.route('/api/api-sources', methods=['GET'])
def api_api_sources():
    """获取可用的下载接口列表"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    local_cfg = _read_local_config()
    mode = str(local_cfg.get('api_base_url_mode', 'auto') or 'auto').lower()
    sources = _get_api_sources()

    # 并发探测所有节点
    timeout = min(float(CONFIG.get('request_timeout', 10) or 10), 2.0)
    probed = []
    with ThreadPoolExecutor(max_workers=min(10, len(sources) or 1)) as ex:
        fut_map = {ex.submit(_probe_api_source, s['base_url'], timeout, s.get('config_supports_full_download')): s for s in sources}
        for fut in as_completed(fut_map):
            src = fut_map[fut]
            try:
                probe = fut.result()
            except Exception as e:
                probe = {'available': False, 'latency_ms': None, 'status_code': None, 'error': str(e)}
            probed.append({**src, **probe})

    # 更新节点探测缓存
    update_probed_cache(probed)

    # 按优先级排序
    probed.sort(key=lambda x: (
        not x.get('available'),
        not x.get('supports_full_download', False),
        x.get('latency_ms') or 999999
    ))

    # 自动模式下选择最快的可用节点
    current = _normalize_base_url(str(CONFIG.get('api_base_url', '') or ''))
    if mode == 'auto':
        available = [p for p in probed if p.get('available')]
        if available:
            best = available[0]['base_url']
            if best != current:
                _apply_api_base_url(best)
                _write_local_config({'api_base_url_mode': 'auto', 'api_base_url': best})
            current = best

    return jsonify({
        'success': True,
        'mode': mode,
        'current': current,
        'sources': probed
    })

@app.route('/api/api-sources/select', methods=['POST'])
def api_api_sources_select():
    """选择下载接口"""
    data = request.get_json() or {}
    mode = str(data.get('mode', 'auto') or 'auto').lower()

    if mode not in ['auto', 'manual']:
        mode = 'auto'

    if mode == 'auto':
        selected = _ensure_api_base_url(force_mode='auto')
        if not selected:
            return jsonify({'success': False, 'message': '未找到可用接口'}), 500
        _write_local_config({'api_base_url_mode': 'auto', 'api_base_url': selected})
        return jsonify({'success': True, 'mode': 'auto', 'current': selected})

    # manual
    base_url = _normalize_base_url(str(data.get('base_url', '') or ''))
    if not base_url:
        return jsonify({'success': False, 'message': 'base_url required'}), 400

    probe = _probe_api_source(base_url)
    if not probe.get('available'):
        err = probe.get('error') or 'unavailable'
        return jsonify({'success': False, 'message': f'接口不可用: {base_url} ({err})', 'probe': probe}), 400

    _apply_api_base_url(base_url)
    _write_local_config({'api_base_url_mode': 'manual', 'api_base_url': base_url})

    return jsonify({'success': True, 'mode': 'manual', 'current': base_url, 'probe': probe})

# 注册拆分后的路由 Blueprint
from .book_routes import book_bp
app.register_blueprint(book_bp)

# 注册批量下载路由 Blueprint
from .batch_routes import batch_bp
app.register_blueprint(batch_bp)

@app.route('/api/language', methods=['GET', 'POST'])
def api_language():
    """获取/设置语言配置"""
    from locales import get_current_lang, set_current_lang
    
    if request.method == 'GET':
        return jsonify({'language': get_current_lang()})
    else:
        data = request.get_json()
        lang = data.get('language', 'zh')
        if lang not in ['zh', 'en']:
            lang = 'zh'
        if set_current_lang(lang):
            return jsonify({'success': True, 'language': lang})
        else:
            return jsonify({'success': False, 'message': 'Failed to save language'}), 500

# 注册配置路由 Blueprint
from .config_routes import config_bp
app.register_blueprint(config_bp)

# 更新相关路由
from .update_routes import init_update_routes
init_update_routes(
    app,
    config_file=CONFIG_FILE,
    get_default_download_path=get_default_download_path,
    update_download_worker=update_download_worker,
    get_update_download_status=get_update_download_status,
)


if __name__ == '__main__':
    print(f'配置文件位置: {CONFIG_FILE}')
    print('Web服务器已启动')
    app.run(host='127.0.0.1', port=5000, debug=False)
