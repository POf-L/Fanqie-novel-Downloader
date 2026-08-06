import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish-unsigned-channel.py"
SPEC = importlib.util.spec_from_file_location("publish_unsigned_channel", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PublishUnsignedChannelTest(unittest.TestCase):
    def source(self, tag="unsigned-v2099.1.1-r1", published="2099-01-01T00:00:00Z"):
        return {
            "id": 10,
            "tag_name": tag,
            "target_commitish": "abc123",
            "draft": False,
            "prerelease": False,
            "published_at": published,
            "assets": [
                {"name": "latest.json"},
                {"name": "app.exe.sig"},
                {
                    "name": "app.exe",
                    "browser_download_url": f"https://github.com/o/r/releases/download/{tag}/app.exe",
                },
            ],
        }

    def test_select_source_requires_unsigned_tag_and_updater_assets(self):
        valid = self.source()
        newer_invalid = self.source("unsigned-v2100.1.1-r2", "2100-01-01T00:00:00Z")
        newer_invalid["assets"] = [{"name": "app.exe"}]
        signed = self.source("v2101.1.1", "2101-01-01T00:00:00Z")
        prerelease = self.source(
            "unsigned-v2102.1.1-r3", "2102-01-01T00:00:00Z"
        )
        prerelease["prerelease"] = True
        selected = MODULE.select_source([newer_invalid, signed, prerelease, valid])
        self.assertEqual(selected["tag_name"], valid["tag_name"])

    def test_alias_is_prerelease_and_never_competes_for_latest(self):
        captured = {}

        def fake_gh_json(arguments, *, input_text=None):
            captured["arguments"] = arguments
            captured["payload"] = json.loads(input_text)
            return {"id": 20, "tag_name": "unsigned", "assets": []}

        with (
            patch.object(MODULE, "release_by_tag", return_value=None),
            patch.object(MODULE, "gh_json", side_effect=fake_gh_json),
        ):
            MODULE.upsert_alias("o/r", "unsigned", self.source())
        self.assertEqual(captured["payload"]["tag_name"], "unsigned")
        self.assertEqual(captured["payload"]["prerelease"], True)
        self.assertEqual(captured["payload"]["make_latest"], "false")

    def test_metadata_must_keep_source_release_urls_and_signatures(self):
        source = self.source()
        tag = source["tag_name"]
        metadata = {
            "version": "2099.1.1",
            "platforms": {
                "windows-x86_64": {
                    "signature": "signed",
                    "url": f"https://github.com/o/r/releases/download/{tag}/app.exe",
                }
            },
        }
        MODULE.validate_metadata("o/r", source, metadata)
        metadata["platforms"]["windows-x86_64"]["url"] = (
            "https://github.com/o/r/releases/download/unsigned/app.exe"
        )
        with self.assertRaisesRegex(SystemExit, "does not point"):
            MODULE.validate_metadata("o/r", source, metadata)


if __name__ == "__main__":
    unittest.main()
