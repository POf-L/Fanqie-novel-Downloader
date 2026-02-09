#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传 runtime manifest 文件到 GitHub 发布版本
需要安装 PyGitHub: pip install PyGitHub
"""

import os
import sys
from pathlib import Path

try:
    from github import Github
    from github.GithubException import GithubException
except ImportError:
    print("❌ 需要安装 PyGitHub: pip install PyGitHub")
    sys.exit(1)

def upload_manifests_to_release():
    """上传 manifest 文件到发布版本"""
    
    # 获取 GitHub token
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ 请设置 GITHUB_TOKEN 环境变量")
        print("   或在 GitHub 上创建 Personal Access Token")
        sys.exit(1)
    
    # 仓库信息
    repo_name = "POf-L/Fanqie-novel-Downloader"
    
    print("=== 上传 Runtime Manifest 文件 ===")
    print(f"仓库: {repo_name}")
    
    try:
        # 连接 GitHub
        g = Github(token)
        repo = g.get_repo(repo_name)
        
        # 获取最新发布
        release = repo.get_latest_release()
        print(f"最新发布: {release.tag_name}")
        
        # 查找 manifest 文件
        manifest_files = list(Path(".").glob("runtime-manifest-*.json"))
        if not manifest_files:
            print("❌ 未找到 manifest 文件")
            sys.exit(1)
        
        print(f"找到 {len(manifest_files)} 个 manifest 文件:")
        for file in manifest_files:
            print(f"  - {file.name}")
        
        # 上传每个文件
        uploaded_count = 0
        for manifest_file in manifest_files:
            print(f"\n上传 {manifest_file.name}...")
            
            try:
                # 检查文件是否已存在
                existing_assets = [asset for asset in release.get_assets() 
                                 if asset.name == manifest_file.name]
                
                if existing_assets:
                    print(f"  - 文件已存在，删除旧版本...")
                    existing_assets[0].delete()
                
                # 上传新文件
                with open(manifest_file, "rb") as f:
                    content = f.read()
                
                release.upload_asset(
                    content,
                    manifest_file.name,
                    content_type="application/json"
                )
                
                print(f"  ✅ 上传成功")
                uploaded_count += 1
                
            except GithubException as e:
                print(f"  ❌ 上传失败: {e}")
        
        print(f"\n=== 完成 ===")
        print(f"成功上传 {uploaded_count}/{len(manifest_files)} 个文件")
        
        if uploaded_count > 0:
            print(f"\n🎉 Runtime manifest 文件已上传到发布版本!")
            print(f"现在启动器应该能够正常工作了。")
        
    except GithubException as e:
        print(f"❌ GitHub API 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        sys.exit(1)

def main():
    print("=== GitHub Runtime Manifest 上传工具 ===")
    print("将生成的 manifest 文件上传到 GitHub 发布版本")
    
    if not os.environ.get("GITHUB_TOKEN"):
        print("\n📝 使用说明:")
        print("1. 在 GitHub 上创建 Personal Access Token:")
        print("   - 访问 https://github.com/settings/tokens")
        print("   - 点击 'Generate new token'")
        print("   - 选择 'repo' 权限")
        print("2. 设置环境变量:")
        print("   - Windows: set GITHUB_TOKEN=your_token_here")
        print("   - Linux/Mac: export GITHUB_TOKEN=your_token_here")
        print("3. 重新运行此脚本")
        sys.exit(1)
    
    upload_manifests_to_release()

if __name__ == "__main__":
    main()
