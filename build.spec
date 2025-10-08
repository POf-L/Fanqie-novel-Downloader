# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files
from build_config import get_hidden_imports
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

# Ensure PyInstaller searches the project root for local modules
# Use __file__ to get the directory where build.spec is located
spec_root = os.path.dirname(os.path.abspath(SPECPATH))
project_root = spec_root

block_cipher = None

# 收集 fake_useragent 数据文件
fake_useragent_datas = collect_data_files('fake_useragent')

# 分析需要包含的模块
a = Analysis(
    ['gui.py'],
    pathex=[project_root],
    binaries=[
        # 确保Pillow的二进制文件被包含
    ],
    datas=[
        # Python 模块应该通过 hiddenimports 打包，不要放在 datas 中
    ] + fake_useragent_datas,
    hiddenimports=(get_hidden_imports() + ['updater', 'external_updater', 'version']),  # 自动从 requirements.txt 读取依赖，并强制包含本地更新模块
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
 