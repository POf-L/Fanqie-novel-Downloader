#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时修复脚本：为现有发布版本创建 runtime manifest
指向现有的独立版本文件作为临时解决方案
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests

def get_latest_release():
    """获取最新发布信息"""
    url = "https://api.github.com/repos/POf-L/Fanqie-novel-Downloader/releases/latest"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"获取发布信息失败: {e}")
        return None

def generate_manifest_for_existing_file(release_data, platform, filename):
    """为现有文件生成 manifest"""
    print(f"\n=== 生成 {platform} 平台 manifest (使用 {filename}) ===")
    
    # 查找对应的文件
    file_url = None
    file_size = None
    
    for asset in release_data.get("assets", []):
        if asset.get("name") == filename:
            file_url = asset.get("browser_download_url")
            file_size = asset.get("size")
            break
    
    if not file_url:
        print(f"❌ 未找到文件: {filename}")
        return None
    
    print(f"✓ 找到文件: {filename}")
    print(f"  - URL: {file_url}")
    print(f"  - 大小: {file_size:,} bytes")
    
    # 下载文件计算 SHA256
    print("下载文件并计算 SHA256...")
    try:
        response = requests.get(file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        hasher = hashlib.sha256()
        downloaded_size = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                hasher.update(chunk)
                downloaded_size += len(chunk)
        
        sha256_hash = hasher.hexdigest()
        print(f"✓ 下载完成: {downloaded_size:,} bytes")
        print(f"✓ SHA256: {sha256_hash}")
        
        # 验证大小
        if downloaded_size != file_size:
            print(f"⚠️  警告: 下载大小 ({downloaded_size}) 与预期大小 ({file_size}) 不匹配")
        
    except Exception as e:
        print(f"❌ 下载或计算失败: {e}")
        return None
    
    # 生成 manifest
    tag_name = release_data.get("tag_name", "unknown")
    repo_name = "POf-L/Fanqie-novel-Downloader"
    
    manifest = {
        "manifest_version": "1",
        "platform": platform,
        "runtime_version": tag_name,
        "runtime_archive_name": filename,
        "runtime_archive_url": file_url,
        "runtime_archive_sha256": sha256_hash,
        "runtime_archive_size": downloaded_size,
        "min_launcher_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": f"临时修复：使用 {filename} 作为 runtime 替代",
    }
    
    # 保存 manifest
    output_file = f"runtime-manifest-{platform}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 已生成 manifest: {output_file}")
    print(f"  - 平台: {manifest['platform']}")
    print(f"  - 版本: {manifest['runtime_version']}")
    print(f"  - 文件大小: {manifest['runtime_archive_size']:,} bytes")
    
    return output_file

def main():
    print("=== Fanqie Novel Downloader 临时 Runtime Manifest 生成器 ===")
    print("使用现有文件创建临时 runtime manifest")
    
    # 获取最新发布信息
    print("\n获取最新发布信息...")
    release_data = get_latest_release()
    if not release_data:
        print("❌ 无法获取发布信息，退出")
        sys.exit(1)
    
    tag_name = release_data.get("tag_name", "unknown")
    print(f"✓ 最新版本: {tag_name}")
    
    # 定义平台和对应的现有文件
    platforms = [
        ("windows-x64", "TomatoNovelDownloader-Standalone.exe"),
        ("linux-x64", "TomatoNovelDownloader-linux"),
        ("macos-x64", "TomatoNovelDownloader-macos"),
        ("termux-arm64", "TomatoNovelDownloader-termux-arm64"),
    ]
    
    generated_files = []
    
    # 为每个平台生成 manifest
    for platform, filename in platforms:
        manifest_file = generate_manifest_for_existing_file(release_data, platform, filename)
        if manifest_file:
            generated_files.append(manifest_file)
    
    print(f"\n=== 完成 ===")
    print(f"成功生成 {len(generated_files)} 个临时 manifest 文件:")
    for file in generated_files:
        print(f"  - {file}")
    
    if generated_files:
        print(f"\n📝 使用说明:")
        print(f"1. 这些是临时修复文件，使用现有的独立版本作为 runtime")
        print(f"2. 需要手动上传到 GitHub 发布版本")
        print(f"3. 或者可以等待下一次完整的自动构建")
        print(f"4. 启动器应该能够使用这些 manifest 正常工作")

if __name__ == "__main__":
    main()
