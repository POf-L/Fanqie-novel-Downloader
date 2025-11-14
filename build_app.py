#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Python编译脚本
用于GitHub Actions中的可执行文件编译
支持不同变体（release/debug）和平台特定的可执行文件命名
包含了原 build_config.py 的功能
"""

import subprocess
import sys
import os
import shutil
import argparse
import re
from pathlib import Path

# 导入编码工具（如果存在）
try:
    from encoding_utils import safe_print, setup_utf8_encoding
    # 确保UTF-8编码设置
    setup_utf8_encoding()
    # 使用安全的print函数
    print = safe_print
except ImportError:
    # 如果编码工具不存在，使用基本的编码设置
    if sys.platform.startswith('win'):
        import locale
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            except locale.Error:
                pass  # 使用默认编码


def parse_requirements(requirements_file='requirements.txt'):
    """
    解析 requirements.txt 文件，提取所有包名
    
    Args:
        requirements_file: requirements.txt 文件路径
        
    Returns:
        list: 包名列表
    """
    packages = []
    req_path = Path(__file__).parent / requirements_file
    
    if not req_path.exists():
        return packages
    
    with open(req_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue
            
            # 提取包名（去除版本约束）
            # 支持格式：package, package==1.0, package>=1.0,<2.0
            match = re.match(r'^([a-zA-Z0-9_-]+)', line)
            if match:
                packages.append(match.group(1))
    
    return packages


# 某些包需要显式导入子模块
PACKAGE_SUBMODULES = {
    'requests': [
        'requests.adapters',
        'requests.auth',
        'requests.cookies',
        'requests.exceptions',
        'requests.models',
        'requests.sessions',
        'requests.structures',
        'requests.utils',
        'requests.api',
        'requests.compat',
        'requests.help',
        'requests.hooks',
        'requests.packages',
        'requests.status_codes',
    ],
    'urllib3': [
        'urllib3.util',
        'urllib3.util.retry',
        'urllib3.util.ssl_',
        'urllib3.util.timeout',
        'urllib3.util.url',
        'urllib3.connection',
        'urllib3.connectionpool',
        'urllib3.poolmanager',
        'urllib3.response',
        'urllib3.exceptions',
        'urllib3._collections',
    ],
    'packaging': [
        'packaging.version',
        'packaging.specifiers',
        'packaging.requirements',
        'packaging.markers',
        'packaging.utils',
        'packaging.tags',
    ],
    'PIL': [
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'PIL.ImageFile',
        'PIL.ImageFont',
        'PIL.ImageOps',
        'PIL.JpegImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.WebPImagePlugin',
        'PIL._imaging',
    ],
    'beautifulsoup4': [
        'bs4',
    ],
    'fake_useragent': [
        'fake_useragent.data',
    ],
    'pillow_heif': [
        'pillow_heif.heif',
        'pillow_heif.misc',
        'pillow_heif.options',
    ],
}

# 标准库模块（需要显式导入的）
STDLIB_MODULES = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.font',
    'tkinter.scrolledtext',
    'threading',
    'json',
    'os',
    'sys',
    'time',
    're',
    'base64',
    'gzip',
    'urllib.parse',
    'concurrent.futures',
    'collections',
    'typing',
    'signal',
    'random',
    'io',
    'tempfile',
    'zipfile',
    'shutil',
    'subprocess',
    'datetime',
]

# 包名映射（处理特殊情况）
PACKAGE_NAME_MAPPING = {
    'pillow': 'PIL',
    'fake-useragent': 'fake_useragent',
    'beautifulsoup4': 'bs4',
}

# 隐式依赖（某些包的运行时依赖）
IMPLICIT_DEPENDENCIES = [
    'charset_normalizer',
    'idna',
    'certifi',
]


def get_hidden_imports():
    """
    获取所有需要的 hiddenimports
    
    Returns:
        list: 完整的 hiddenimports 列表
    """
    packages = parse_requirements()
    hidden_imports = []
    
    # 添加基础包
    for pkg in packages:
        pkg_lower = pkg.lower()
        
        # 处理特殊包名映射
        if pkg_lower in PACKAGE_NAME_MAPPING:
            mapped_pkg = PACKAGE_NAME_MAPPING[pkg_lower]
            hidden_imports.append(mapped_pkg)
            pkg = mapped_pkg
        else:
            # 将连字符转换为下划线
            pkg = pkg.replace('-', '_')
            hidden_imports.append(pkg)
        
        # 添加已知的子模块
        if pkg in PACKAGE_SUBMODULES:
            hidden_imports.extend(PACKAGE_SUBMODULES[pkg])
    
    # 添加标准库模块
    hidden_imports.extend(STDLIB_MODULES)
    
    # 添加隐式依赖
    hidden_imports.extend(IMPLICIT_DEPENDENCIES)
    
    # 加入本地模块（PyInstaller 有时不会解析到函数/方法内的导入）
    # 确保配置模块被正确打包
    hidden_imports.extend([
        'config',
    ])

    # 去重并排序
    hidden_imports = sorted(set(hidden_imports))
    
    return hidden_imports


def build_executable(variant="release", executable_name=None):
    """编译可执行文件
    
    Args:
        variant: 构建变体 ('release' 或 'debug')
        executable_name: 自定义可执行文件名称（不包含扩展名）
    
    Returns:
        tuple: (success, built_name, target_name)
            - success: 构建是否成功
            - built_name: spec文件中定义的原始名称
            - target_name: 期望的最终名称
    """
    print(f"Starting build process for {variant} variant...")
    
    # 确定目标可执行文件名称
    if executable_name:
        target_name = executable_name
    else:
        target_name = "TomatoNovelDownloader-debug" if variant == "debug" else "TomatoNovelDownloader"
    
    # 检查是否有对应的spec文件
    spec_file = "debug.spec" if variant == "debug" else "build.spec"
    
    if os.path.exists(spec_file):
        print(f"Using {spec_file} configuration file")
        # 使用spec文件时不能使用--name参数，需要使用spec中定义的名称
        cmd = [sys.executable, "-m", "PyInstaller", spec_file, "--clean", "--noconfirm"]
        # spec文件中定义的默认名称
        built_name = "TomatoNovelDownloader-debug" if variant == "debug" else "TomatoNovelDownloader"
    else:
        print(f"{spec_file} not found, using default configuration")
        
        # 构建基础命令
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            f"--name={target_name}",
        ]
        
        # 根据变体选择窗口模式或控制台模式
        if variant == "debug":
            cmd.append("--console")
        else:
            cmd.append("--windowed")
        
        # 添加隐藏导入（自动从 requirements.txt 读取）
        hidden_imports = get_hidden_imports()
        
        for import_name in hidden_imports:
            cmd.extend(["--hidden-import", import_name])
        
        # 添加数据收集
        cmd.extend(["--collect-data", "fake_useragent"])
        cmd.extend(["--collect-submodules", "PIL"])
        
        # 添加入口文件
        cmd.append("gui.py")
        
        # 没有使用spec文件时，built_name和target_name相同
        built_name = target_name
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        print("Build successful")
        print(result.stdout)
        # 如果使用spec文件，返回built_name和target_name
        if os.path.exists(spec_file):
            return True, built_name, target_name
        else:
            return True, target_name, target_name
    except subprocess.CalledProcessError as e:
        print("Build failed")
        print(f"Error output: {e.stderr}")
        if os.path.exists(spec_file):
            return False, built_name, target_name
        else:
            return False, target_name, target_name

def check_output(expected_name):
    """检查编译输出
    
    Args:
        expected_name: 期望的可执行文件名称（不包含扩展名）
    """
    print("Checking build output...")
    if os.path.exists("dist"):
        files = os.listdir("dist")
        print(f"dist directory contents: {files}")
        
        # 检查可执行文件
        exe_name = f"{expected_name}.exe" if os.name == "nt" else expected_name
        exe_path = os.path.join("dist", exe_name)
        
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path)
            print(f"Executable created successfully: {exe_name} ({size} bytes)")
            return True
        else:
            print(f"Executable not found: {exe_path}")
            return False
    else:
        print("dist directory does not exist")
        return False

def rename_executable(current_name, target_name):
    """重命名可执行文件
    
    Args:
        current_name: 当前文件名（不包含扩展名）
        target_name: 目标文件名（不包含扩展名）
    """
    if current_name == target_name:
        return True
        
    ext = ".exe" if os.name == "nt" else ""
    current_path = os.path.join("dist", f"{current_name}{ext}")
    target_path = os.path.join("dist", f"{target_name}{ext}")
    
    if os.path.exists(current_path):
        try:
            os.rename(current_path, target_path)
            print(f"Renamed {current_name}{ext} to {target_name}{ext}")
            return True
        except OSError as e:
            print(f"Failed to rename executable: {e}")
            return False
    else:
        print(f"Source file not found: {current_path}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Build Tomato Novel Downloader")
    parser.add_argument("--variant", choices=["release", "debug"], default="release",
                       help="Build variant (release or debug)")
    parser.add_argument("--name", type=str, help="Custom executable name (without extension)")
    
    args = parser.parse_args()
    
    # 构建可执行文件
    success, built_name, target_name = build_executable(args.variant, args.name)
    
    if success:
        # 先检查构建输出
        if check_output(built_name):
            # 如果built_name和target_name不同，需要重命名
            if built_name != target_name:
                if rename_executable(built_name, target_name):
                    print(f"Build completed successfully! Final executable: {target_name}")
                    return True
                else:
                    print("Build successful but renaming failed")
                    return False
            else:
                print(f"Build completed successfully! Executable: {built_name}")
                return True
        else:
            print("Build output check failed")
            return False
    else:
        print("Build failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 