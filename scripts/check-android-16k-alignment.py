#!/usr/bin/env python3
"""检查 Android APK 是否满足 16 KiB 页大小要求。

Android 15 起支持 16 KiB 页大小的设备，Google Play 要求面向 Android 15+ 的应用
兼容 16 KiB 页。64 位 ABI（arm64-v8a、x86_64）里的每个 .so 需要：

1. ELF：所有 PT_LOAD 段的 p_align >= 16384；
2. ZIP：以 STORED（不压缩）方式放进 APK 的 .so，数据起点要按 16384 字节对齐
   （压缩存放的 .so 安装时会解压，不受这一条约束）。

32 位 ABI（armeabi-v7a、x86）不受该要求约束，只做统计、不判失败。

默认只输出 ::warning:: 并以 0 退出；先跑一两个版本确认都通过，再在 workflow 里加
--strict 改成失败。不依赖 build-tools，本地也能直接跑：

    python3 scripts/check-android-16k-alignment.py dist/android/*.apk
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

PAGE_16K = 16384
ABIS_64 = ("arm64-v8a", "x86_64")
PT_LOAD = 1
LOCAL_HEADER_SIZE = 30


def elf_load_alignments(data: bytes) -> list[int]:
    """返回 ELF 里每个 PT_LOAD 段的 p_align；不是合法 ELF 时抛 ValueError。"""
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise ValueError("不是 ELF 文件")
    elf_class, endian = data[4], data[5]
    if endian not in (1, 2):
        raise ValueError("未知的字节序")
    order = "<" if endian == 1 else ">"
    if elf_class == 2:  # ELF64
        phoff = struct.unpack_from(order + "Q", data, 0x20)[0]
        phentsize, phnum = struct.unpack_from(order + "HH", data, 0x36)
        entry, type_at, align_at = order + "I", 0, 0x30
        align_fmt = order + "Q"
    elif elf_class == 1:  # ELF32
        phoff = struct.unpack_from(order + "I", data, 0x1C)[0]
        phentsize, phnum = struct.unpack_from(order + "HH", data, 0x2A)
        entry, type_at, align_at = order + "I", 0, 0x1C
        align_fmt = order + "I"
    else:
        raise ValueError("未知的 ELF class")
    alignments = []
    for index in range(phnum):
        base = phoff + index * phentsize
        if base + phentsize > len(data):
            raise ValueError("程序头越界")
        if struct.unpack_from(entry, data, base + type_at)[0] == PT_LOAD:
            alignments.append(struct.unpack_from(align_fmt, data, base + align_at)[0])
    return alignments


def stored_data_offset(apk: Path, info: zipfile.ZipInfo) -> int:
    """STORED 条目在 APK 文件里的数据起点（本地文件头之后）。"""
    with apk.open("rb") as handle:
        handle.seek(info.header_offset)
        header = handle.read(LOCAL_HEADER_SIZE)
    if len(header) != LOCAL_HEADER_SIZE or header[:4] != b"PK\x03\x04":
        raise ValueError("本地文件头损坏")
    name_length, extra_length = struct.unpack_from("<HH", header, 26)
    return info.header_offset + LOCAL_HEADER_SIZE + name_length + extra_length


def check_apk(apk: Path) -> tuple[list[str], int]:
    """返回（问题列表, 检查过的 64 位 .so 数量）。"""
    problems: list[str] = []
    checked = 0
    with zipfile.ZipFile(apk) as archive:
        for info in archive.infolist():
            parts = info.filename.split("/")
            if len(parts) != 3 or parts[0] != "lib" or not parts[2].endswith(".so"):
                continue
            if parts[1] not in ABIS_64:
                continue
            checked += 1
            try:
                alignments = elf_load_alignments(archive.read(info))
            except ValueError as error:
                problems.append(f"{info.filename}: 无法解析 ELF（{error}）")
                continue
            bad = sorted({value for value in alignments if value < PAGE_16K})
            if not alignments:
                problems.append(f"{info.filename}: 没有 PT_LOAD 段")
            elif bad:
                problems.append(
                    f"{info.filename}: LOAD 段对齐 {', '.join(hex(v) for v in bad)} < 0x4000"
                )
            if info.compress_type == zipfile.ZIP_STORED:
                offset = stored_data_offset(apk, info)
                if offset % PAGE_16K:
                    problems.append(
                        f"{info.filename}: 未压缩存放但数据偏移 {offset} 不是 16 KiB 的整数倍"
                    )
    return problems, checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("apks", nargs="+", type=Path)
    parser.add_argument("--strict", action="store_true", help="有问题时以 1 退出")
    args = parser.parse_args(argv)

    level = "error" if args.strict else "warning"
    failed = False
    for apk in args.apks:
        try:
            problems, checked = check_apk(apk)
        except (OSError, zipfile.BadZipFile, ValueError) as error:
            problems, checked = [f"无法读取 APK（{error}）"], 0
        if problems:
            failed = True
            for problem in problems:
                print(f"::{level}::16 KiB 对齐：{apk.name}: {problem}")
        else:
            print(f"16 KiB 对齐通过：{apk.name}（64 位 .so {checked} 个）")
    return 1 if failed and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
