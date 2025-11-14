# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

# Try to import build_app, but fallback to manual list if it fails
try:
    from build_app import get_hidden_imports
    extra_hidden = get_hidden_imports()
except ImportError:
    print("Warning: build_app.py not found, using minimal imports")
    extra_hidden = []

# Ensure PyInstaller searches the project root for local modules
# Fix the path to ensure it works in GitHub Actions
if 'SPECPATH' in locals():
    project_root = os.path.dirname(os.path.abspath(SPECPATH))
else:
    project_root = os.path.dirname(os.path.abspath(__file__))

block_cipher = None

#  fake_useragent
fake_useragent_datas = collect_data_files('fake_useragent')
# 分析需要包含的模块
a = Analysis(
    ['gui.py'],
    pathex=[project_root],
    binaries=[
        # 确保Pillow的二进制文件被包含
    ],
    datas=[
        ('config.py', '.'),
    ] + fake_useragent_datas,
    hiddenimports=(extra_hidden + ['config']),  # 自动从 requirements.txt 读取依赖，并强制包含本地配置模块
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[
        'matplotlib',
        'pandas',
        'numpy',
        'scipy',
        'bokeh',
        'h5py',
        'lz4',
        'jinja2',
        'cloudpickle',
        'dask',
        'distributed',
        'fsspec',
        'pyarrow',
        'pytz'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TomatoNovelDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用UPX压缩以避免Windows构建问题
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 设置为窗口模式
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
 