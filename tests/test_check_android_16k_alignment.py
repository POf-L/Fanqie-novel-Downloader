import importlib.util
import io
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-android-16k-alignment.py"
spec = importlib.util.spec_from_file_location("check_android_16k", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def elf64(*aligns):
    """最小的 ELF64 小端文件：每个 align 对应一个 PT_LOAD，外加一个 PT_DYNAMIC。"""
    headers = [(1, value) for value in aligns] + [(2, 8)]
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", header, 0x20, 64)
    struct.pack_into("<HH", header, 0x36, 56, len(headers))
    body = b"".join(struct.pack("<IIQQQQQQ", kind, 5, 0, 0, 0, 0, 0, align) for kind, align in headers)
    return bytes(header) + body


def elf32(*aligns):
    header = bytearray(52)
    header[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<I", header, 0x1C, 52)
    struct.pack_into("<HH", header, 0x2A, 32, len(aligns))
    body = b"".join(struct.pack("<IIIIIIII", 1, 0, 0, 0, 0, 0, 5, align) for align in aligns)
    return bytes(header) + body


class Android16kAlignmentTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def apk(self, entries, *, align_stored=True):
        """entries: (路径, 内容, 是否 STORED)。align_stored 时用 extra 字段把 STORED 数据对齐到 16 KiB。"""
        path = self.directory / f"app-{len(list(self.directory.iterdir()))}.apk"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data, stored in entries:
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
                if stored and align_stored:
                    offset = archive.fp.tell() + 30 + len(name.encode())
                    padding = (-(offset + 4)) % 16384
                    info.extra = struct.pack("<HH", 0xD935, padding) + b"\0" * padding
                archive.writestr(info, data)
        return path

    def test_aligned_64bit_libraries_pass(self):
        apk = self.apk(
            [
                ("AndroidManifest.xml", b"x", False),
                ("lib/arm64-v8a/libapp.so", elf64(0x4000, 0x10000), True),
                ("lib/x86_64/libapp.so", elf64(0x4000), False),
            ]
        )
        self.assertEqual(checker.check_apk(apk), ([], 2))

    def test_4k_load_segment_is_reported(self):
        apk = self.apk([("lib/arm64-v8a/libapp.so", elf64(0x1000, 0x4000), False)])
        problems, checked = checker.check_apk(apk)
        self.assertEqual(checked, 1)
        self.assertEqual(len(problems), 1)
        self.assertIn("0x1000", problems[0])

    def test_misaligned_stored_library_is_reported(self):
        apk = self.apk(
            [("lib/arm64-v8a/libapp.so", elf64(0x4000), True)], align_stored=False
        )
        problems, _ = checker.check_apk(apk)
        self.assertEqual(len(problems), 1)
        self.assertIn("16 KiB", problems[0])

    def test_32bit_abis_are_not_checked(self):
        apk = self.apk([("lib/armeabi-v7a/libapp.so", elf32(0x1000), True)], align_stored=False)
        self.assertEqual(checker.check_apk(apk), ([], 0))

    def test_elf32_parser(self):
        self.assertEqual(checker.elf_load_alignments(elf32(0x1000, 0x4000)), [0x1000, 0x4000])

    def test_garbage_library_is_reported(self):
        apk = self.apk([("lib/x86_64/libapp.so", b"not an elf", False)])
        problems, _ = checker.check_apk(apk)
        self.assertIn("无法解析 ELF", problems[0])

    def test_warning_mode_exits_zero_and_strict_mode_fails(self):
        apk = self.apk([("lib/arm64-v8a/libapp.so", elf64(0x1000), False)])
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(checker.main([str(apk)]), 0)
        self.assertIn("::warning::16 KiB 对齐", output.getvalue())
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--strict", str(apk)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error::16 KiB 对齐", result.stdout)


if __name__ == "__main__":
    unittest.main()
