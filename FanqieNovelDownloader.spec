# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Administrator\\Desktop\\Fanqie-Tomato-Downloader-main\\gui.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Administrator\\Desktop\\Fanqie-Tomato-Downloader-main\\assets', 'assets'), ('C:\\Program Files\\Python313\\Lib\\site-packages\\customtkinter', 'customtkinter')],
    hiddenimports=['requests', 'bs4', 'lxml', 'ebooklib', 'ebooklib.epub', 'tqdm', 'json', 'threading', 'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox', 'customtkinter', 'PIL', 'config', 'settings', 'library', 'reader', 'splash', 'request_handler'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FanqieNovelDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
