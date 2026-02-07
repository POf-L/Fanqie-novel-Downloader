# -*- coding: utf-8 -*-
import json
import hashlib
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests


class CloudUpdater:
    def __init__(self, project_root: Path, manifest_url: str, timeout: int = 10):
        self.project_root = project_root.resolve()
        self.manifest_url = manifest_url
        self.timeout = timeout

        self.update_root = self.project_root / "cache" / "cloud_update"
        self.cache_root = self.update_root / "files"
        self.backup_root = self.update_root / "backups"
        self.local_manifest_path = self.update_root / "manifest_cache.json"
        self.local_versions_path = self.update_root / "versions.json"

        self.update_root.mkdir(parents=True, exist_ok=True)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def run(self):
        result = {
            "manifest_source": None,
            "updated": [],
            "skipped": [],
            "failed": [],
        }

        manifest = self._load_manifest()
        if manifest is None:
            result["failed"].append({"reason": "manifest_unavailable"})
            return result

        files = manifest.get("files", [])
        local_versions = self._read_json(self.local_versions_path, default={})
        backup_session = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        for item in files:
            try:
                self._validate_manifest_item(item)
                rel_path = item["path"]
                remote_version = str(item["version"])
                remote_sha = item["sha256"].lower()
                remote_url = item["url"]

                target_path = self._safe_target_path(rel_path)
                local_info = local_versions.get(rel_path, {})
                local_version = str(local_info.get("version", ""))
                local_sha = str(local_info.get("sha256", "")).lower()

                if local_version == remote_version and local_sha == remote_sha and target_path.exists():
                    result["skipped"].append({"path": rel_path, "reason": "same_version"})
                    continue

                content = self._download_with_cache(rel_path, remote_url)
                actual_sha = hashlib.sha256(content).hexdigest().lower()
                if actual_sha != remote_sha:
                    raise ValueError(f"sha256 mismatch: expected={remote_sha}, actual={actual_sha}")

                if target_path.exists():
                    self._backup_file(target_path, backup_session)

                self._atomic_write(target_path, content)

                local_versions[rel_path] = {
                    "version": remote_version,
                    "sha256": remote_sha,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                result["updated"].append({"path": rel_path, "version": remote_version})
            except Exception as exc:
                result["failed"].append({"path": item.get("path"), "reason": str(exc)})

        self._atomic_write_json(self.local_versions_path, local_versions)
        return result

    def _load_manifest(self):
        try:
            resp = requests.get(self.manifest_url, timeout=self.timeout)
            resp.raise_for_status()
            manifest = resp.json()
            self._atomic_write_json(self.local_manifest_path, manifest)
            return manifest
        except Exception:
            return self._read_json(self.local_manifest_path, default=None)

    def _download_with_cache(self, rel_path: str, remote_url: str) -> bytes:
        cache_file = self.cache_root / rel_path
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        resp = requests.get(remote_url, timeout=self.timeout)
        resp.raise_for_status()
        content = resp.content
        self._atomic_write(cache_file, content)
        return content

    def _backup_file(self, target_path: Path, backup_session: str):
        rel = target_path.relative_to(self.project_root)
        backup_file = self.backup_root / backup_session / rel
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_path, backup_file)

    def _safe_target_path(self, rel_path: str) -> Path:
        p = Path(rel_path)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"unsafe path: {rel_path}")
        if p.suffix.lower() != ".py":
            raise ValueError(f"only .py files are allowed: {rel_path}")

        target = (self.project_root / p).resolve()
        if not str(target).startswith(str(self.project_root)):
            raise ValueError(f"path out of project: {rel_path}")
        return target

    def _validate_manifest_item(self, item: dict):
        for key in ("path", "version", "sha256", "url"):
            if key not in item:
                raise ValueError(f"manifest item missing key: {key}")

        parsed = urlparse(item["url"])
        if parsed.scheme not in ("http", "https"):
            raise ValueError("invalid file url scheme")

    @staticmethod
    def _read_json(path: Path, default):
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _atomic_write(path: Path, content: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, dir=str(path.parent)) as tmp:
            tmp.write(content)
            tmp_name = tmp.name
        Path(tmp_name).replace(path)

    def _atomic_write_json(self, path: Path, obj):
        data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self._atomic_write(path, data)

