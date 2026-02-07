# -*- coding: utf-8 -*-
"""云同步模块：用于 GitHub Actions 发布版运行时资源同步。"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


RUNTIME_BASE_ENV = "FANQIE_RUNTIME_BASE"
LOCAL_MANIFEST_FILE = ".cloud_manifest.json"


def _user_data_dir() -> Path:
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "FanqieNovelDownloader"
    return Path.home() / ".fanqie_novel_downloader"


def _runtime_dir() -> Path:
    return _user_data_dir() / "runtime"


def _cache_dir() -> Path:
    return _user_data_dir() / "cloud_sync_cache"


def _is_github_actions_build() -> bool:
    try:
        from config.config import __build_channel__

        return str(__build_channel__).startswith("github-actions")
    except Exception:
        return False


def should_run_cloud_sync() -> bool:
    return bool(getattr(sys, "frozen", False) and _is_github_actions_build())


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_rel_path(path_text: str) -> str:
    normalized = path_text.replace("\\", "/").lstrip("/")
    path_obj = Path(normalized)
    if path_obj.is_absolute() or ".." in path_obj.parts:
        raise ValueError(f"非法路径: {path_text}")
    return "/".join(part for part in path_obj.parts if part not in ("", "."))


def _safe_target(root: Path, rel_path: str) -> Path:
    safe_rel = _safe_rel_path(rel_path)
    target = (root / safe_rel).resolve()
    root_resolved = root.resolve()
    if os.path.commonpath([str(target), str(root_resolved)]) != str(root_resolved):
        raise ValueError(f"越权路径: {rel_path}")
    return target


def _read_json(path: Path) -> Optional[Dict]:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file_obj:
        json.dump(data, file_obj, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _fetch_release_manifest(repo: str, timeout: int = 6) -> Optional[Dict]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FanqieNovelDownloader-CloudSync",
    }
    latest_url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(latest_url, headers=headers, timeout=(2, timeout))
    if response.status_code != 200:
        return None

    release_data = response.json()
    manifest_url = None
    for asset in release_data.get("assets", []):
        if asset.get("name") == "runtime-manifest.json":
            manifest_url = asset.get("browser_download_url")
            break

    if not manifest_url:
        return None

    manifest_response = requests.get(manifest_url, headers=headers, timeout=(2, timeout))
    if manifest_response.status_code != 200:
        return None

    manifest_data = manifest_response.json()
    if not isinstance(manifest_data, dict):
        return None
    if "files" not in manifest_data or not isinstance(manifest_data["files"], list):
        return None
    return manifest_data


def _download_with_cache(url: str, expected_sha256: str, cache_root: Path, timeout: int = 8) -> bytes:
    cache_file = cache_root / "files" / expected_sha256
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "FanqieNovelDownloader-CloudSync"}
    try:
        response = requests.get(url, headers=headers, timeout=(2, timeout))
        response.raise_for_status()
        content = response.content
        if _sha256_bytes(content) != expected_sha256:
            raise ValueError("远程文件哈希不匹配")
        cache_file.write_bytes(content)
        return content
    except Exception:
        if cache_file.exists() and _sha256_file(cache_file) == expected_sha256:
            return cache_file.read_bytes()
        raise


def _backup_file_path(backup_root: Path, rel_path: str) -> Path:
    return backup_root / rel_path


def _collect_remote_files(manifest_data: Dict) -> Dict[str, Dict]:
    remote_files: Dict[str, Dict] = {}
    for item in manifest_data.get("files", []):
        if not isinstance(item, dict):
            continue

        rel_path = _safe_rel_path(str(item.get("path", "")))
        sha256 = str(item.get("sha256", "")).strip().lower()
        file_url = str(item.get("url", "")).strip()
        file_version = str(item.get("version", "")).strip()
        file_size = int(item.get("size", 0) or 0)

        if not rel_path or len(sha256) != 64 or not file_url:
            continue

        remote_files[rel_path] = {
            "sha256": sha256,
            "url": file_url,
            "version": file_version,
            "size": file_size,
        }
    return remote_files


def _sync_runtime_files(runtime_root: Path, manifest_data: Dict, cache_root: Path) -> Tuple[int, int, int]:
    remote_files = _collect_remote_files(manifest_data)

    local_manifest_path = runtime_root / LOCAL_MANIFEST_FILE
    local_manifest = _read_json(local_manifest_path) or {}
    local_files = local_manifest.get("files", {}) if isinstance(local_manifest.get("files"), dict) else {}

    need_download: List[str] = []
    for rel_path, meta in remote_files.items():
        target = _safe_target(runtime_root, rel_path)
        current_sha = _sha256_file(target) if target.exists() else None
        if current_sha != meta["sha256"]:
            need_download.append(rel_path)

    need_delete = [rel_path for rel_path in local_files.keys() if rel_path not in remote_files]

    backup_root = runtime_root / ".cloud_backup" / str(int(time.time()))
    updated_count = 0
    added_count = 0
    deleted_count = 0

    try:
        for rel_path in need_download:
            target = _safe_target(runtime_root, rel_path)
            if target.exists():
                backup_file = _backup_file_path(backup_root, rel_path)
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_file)

        for rel_path in need_delete:
            target = _safe_target(runtime_root, rel_path)
            if target.exists():
                backup_file = _backup_file_path(backup_root, rel_path)
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup_file)

        for rel_path in need_download:
            meta = remote_files[rel_path]
            content = _download_with_cache(meta["url"], meta["sha256"], cache_root)
            target = _safe_target(runtime_root, rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            fd, temp_name = tempfile.mkstemp(prefix="fanqie_sync_", suffix=".tmp")
            os.close(fd)
            temp_file = Path(temp_name)
            try:
                temp_file.write_bytes(content)
                os.replace(temp_file, target)
            finally:
                temp_file.unlink(missing_ok=True)

            if rel_path in local_files:
                updated_count += 1
            else:
                added_count += 1

        for rel_path in need_delete:
            target = _safe_target(runtime_root, rel_path)
            if target.exists():
                target.unlink()
                deleted_count += 1

        new_manifest = {
            "manifest_version": str(manifest_data.get("manifest_version", "1")),
            "release_tag": str(manifest_data.get("release_tag", "")),
            "generated_at": str(manifest_data.get("generated_at", "")),
            "files": remote_files,
            "updated_at": int(time.time()),
        }
        _write_json(local_manifest_path, new_manifest)
    except Exception:
        if backup_root.exists():
            for rel_path in need_download + need_delete:
                backup_file = _backup_file_path(backup_root, rel_path)
                if backup_file.exists():
                    target = _safe_target(runtime_root, rel_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target)
        raise
    finally:
        if backup_root.exists():
            shutil.rmtree(backup_root, ignore_errors=True)

    return updated_count, added_count, deleted_count


def ensure_cloud_runtime_synced(repo: str) -> Dict[str, str]:
    """每次启动执行云同步；失败时尽量回退缓存且不阻塞启动。"""
    runtime_root = _runtime_dir()
    cache_root = _cache_dir()
    runtime_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    cache_manifest = cache_root / "runtime-manifest.json"
    manifest = None
    manifest_source = "remote"

    try:
        manifest = _fetch_release_manifest(repo)
        if manifest:
            _write_json(cache_manifest, manifest)
    except Exception:
        manifest = None

    if not manifest:
        manifest_source = "cache"
        manifest = _read_json(cache_manifest)

    if not manifest:
        bundled_base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        os.environ[RUNTIME_BASE_ENV] = str(bundled_base)
        return {"status": "skip", "message": "无可用清单，使用内置资源"}

    try:
        updated_count, added_count, deleted_count = _sync_runtime_files(runtime_root, manifest, cache_root)
        os.environ[RUNTIME_BASE_ENV] = str(runtime_root)
        return {
            "status": "ok",
            "source": manifest_source,
            "updated": str(updated_count),
            "added": str(added_count),
            "deleted": str(deleted_count),
            "runtime": str(runtime_root),
        }
    except Exception as error:
        if _read_json(runtime_root / LOCAL_MANIFEST_FILE):
            os.environ[RUNTIME_BASE_ENV] = str(runtime_root)
            return {"status": "fallback", "message": f"同步失败，已回退本地缓存: {error}"}

        bundled_base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        os.environ[RUNTIME_BASE_ENV] = str(bundled_base)
        return {"status": "skip", "message": f"同步失败且无本地缓存，使用内置资源: {error}"}

