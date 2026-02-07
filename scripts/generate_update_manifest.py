import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INCLUDE = [
    "main.py",
    "utils",
    "core",
    "web/static",
    "web/templates",
    "config/fanqie.json",
    "assets",
]

DEFAULT_EXCLUDE_PREFIX = [
    ".git/",
    ".github/",
    "cache/",
    "novels/",
    "docs/",
    "test_window_drag/",
    "__pycache__/",
]

DEFAULT_EXCLUDE_SUFFIX = [
    ".pyc",
    ".pyo",
    ".log",
]


def _load_sync_rules(root: Path):
    config_path = root / "config" / "cloud_sync_paths.json"
    if not config_path.exists():
        return DEFAULT_INCLUDE, DEFAULT_EXCLUDE_PREFIX, DEFAULT_EXCLUDE_SUFFIX

    try:
        with config_path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        include = data.get("include", DEFAULT_INCLUDE)
        exclude_prefix = data.get("exclude_prefix", DEFAULT_EXCLUDE_PREFIX)
        exclude_suffix = data.get("exclude_suffix", DEFAULT_EXCLUDE_SUFFIX)
        return include, exclude_prefix, exclude_suffix
    except Exception:
        return DEFAULT_INCLUDE, DEFAULT_EXCLUDE_PREFIX, DEFAULT_EXCLUDE_SUFFIX


def calc_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _iter_sync_files(root: Path, include_rules, exclude_prefix_rules, exclude_suffix_rules):
    visited = set()
    for item in include_rules:
        path = (root / item).resolve()
        if not path.exists():
            continue

        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if _is_excluded(rel, exclude_prefix_rules, exclude_suffix_rules):
                continue
            visited.add(rel)
            yield path, rel
            continue

        for file in path.rglob("*"):
            if not file.is_file():
                continue
            rel = file.relative_to(root).as_posix()
            if rel in visited:
                continue
            if _is_excluded(rel, exclude_prefix_rules, exclude_suffix_rules):
                continue
            visited.add(rel)
            yield file, rel


def _is_excluded(rel_path: str, exclude_prefix_rules, exclude_suffix_rules) -> bool:
    text = rel_path.replace("\\", "/")
    if any(text.startswith(prefix) for prefix in exclude_prefix_rules):
        return True
    return any(text.endswith(suffix) for suffix in exclude_suffix_rules)


def main():
    parser = argparse.ArgumentParser(description="Generate runtime manifest for cloud sync")
    parser.add_argument("--repo", required=True, help="GitHub repo, e.g. owner/repo")
    parser.add_argument("--ref", required=True, help="Git ref, e.g. main or v1.2.3")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--output", default="runtime-manifest.json", help="Manifest output path")
    parser.add_argument("--release-tag", default="", help="Release tag")
    parser.add_argument("--default-version", default="1", help="Default per-file version")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = (root / args.output).resolve()
    include_rules, exclude_prefix_rules, exclude_suffix_rules = _load_sync_rules(root)

    files = []
    for file_path, rel in _iter_sync_files(root, include_rules, exclude_prefix_rules, exclude_suffix_rules):
        sha = calc_sha256(file_path)
        size = file_path.stat().st_size
        url = f"https://raw.githubusercontent.com/{args.repo}/{args.ref}/{rel}"
        files.append(
            {
                "path": rel,
                "version": args.default_version,
                "sha256": sha,
                "url": url,
                "size": size,
            }
        )

    files.sort(key=lambda x: x["path"])
    manifest = {
        "manifest_version": "1",
        "release_tag": args.release_tag,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"manifest generated: {output}")
    print(f"files: {len(files)}")


if __name__ == "__main__":
    main()
