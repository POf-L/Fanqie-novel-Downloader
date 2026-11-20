import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "issue-triage.py"
SPEC = importlib.util.spec_from_file_location("issue_triage", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TriageTest(unittest.TestCase):
    def test_title_prefix_and_existing_label_classify(self):
        self.assertEqual(MODULE.category_for("[Bug] 不能播放", set()), "错误反馈")
        self.assertEqual(MODULE.category_for("[Feature] 增加导出", set()), "增强功能")
        self.assertEqual(MODULE.category_for("[Help] 如何安装", set()), "求助")
        self.assertEqual(MODULE.category_for("issue", {"增强功能"}), "增强功能")
        self.assertIsNone(MODULE.category_for("无分类", set()))

    def test_bug_without_log_is_left_to_dedicated_log_workflow(self):
        self.assertIsNone(MODULE.LOG_PATTERN.search("遇到闪退，见截图"))
        self.assertIsNotNone(MODULE.LOG_PATTERN.search("附件 fanqie-diagnostic-20261120.txt"))
        self.assertIsNotNone(MODULE.LOG_PATTERN.search("https://github.com/user-attachments/files/123/fanqie.log"))

    def test_templates_have_short_chinese_initial_replies(self):
        for label, message in MODULE.MESSAGES.items():
            with self.subTest(label=label):
                self.assertTrue(message)
                self.assertNotIn("TODO", message)
                self.assertTrue(any("\u4e00" <= char <= "\u9fff" for char in message))
                self.assertNotIn("未提供", message)


if __name__ == "__main__":
    unittest.main()
