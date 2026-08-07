#!/usr/bin/env python3
"""Merge a generated unsigned Draft block into existing Release notes."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def load_finalizer():
    path = Path(__file__).with_name("finalize-unsigned-release.py")
    spec = importlib.util.spec_from_file_location("fanqie_unsigned_finalizer", path)
    if spec is None or spec.loader is None:
        fail(f"cannot load unsigned finalizer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"cannot read {path}: {error}")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as output:
            output.write(content)
            temporary = Path(output.name)
        temporary.replace(path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    finalizer = load_finalizer()
    merged = finalizer.merge_unsigned_draft(
        read_text(args.existing), read_text(args.generated)
    )
    atomic_write(args.output, merged)
    print(f"Unsigned Draft notes merged: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
