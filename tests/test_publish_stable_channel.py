import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish-stable-channel.py"
SPEC = importlib.util.spec_from_file_location("publish_stable_channel", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PublishStableChannelTest(unittest.TestCase):
    def signed_release(self, tag="v2099.1.1"):
        source = f"https://github.com/POf-L/Fanqie-novel-Downloader/releases/download/{tag}/"
        return {
            "id": 10,
            "tag_name": tag,
            "target_commitish": "0123456789abcdef0123456789abcdef01234567",
            "draft": False,
            "prerelease": False,
            "published_at": "2099-01-01T00:00:00Z",
            "assets": [
                {"name": "latest.json", "browser_download_url": source + "latest.json"},
                {
                    "name": "FanqieNovelDownloader-tauri-windows-x64-setup.exe.sig",
                    "browser_download_url": source + "FanqieNovelDownloader-tauri-windows-x64-setup.exe.sig",
                },
                {
                    "name": "FanqieNovelDownloader-tauri-windows-x64-setup.exe",
                    "browser_download_url": source + "FanqieNovelDownloader-tauri-windows-x64-setup.exe",
                },
            ],
        }

    def metadata(self, tag="v2099.1.1"):
        source = f"https://github.com/POf-L/Fanqie-novel-Downloader/releases/download/{tag}/"
        return {
            "version": tag.removeprefix("v"),
            "platforms": {
                "windows-x86_64-nsis": {
                    "signature": "signed-entry",
                    "url": source + "FanqieNovelDownloader-tauri-windows-x64-setup.exe",
                }
            },
        }

    def test_selection_excludes_unsigned_and_alias_releases(self):
        signed = self.signed_release()
        releases = [
            {
                "id": 20,
                "tag_name": "unsigned-v2099.1.2-r3",
                "draft": False,
                "prerelease": False,
                "published_at": "2099-02-01T00:00:00Z",
                "assets": [{"name": "Fanqie.exe"}],
            },
            {
                "id": 21,
                "tag_name": "stable",
                "draft": False,
                "prerelease": True,
                "published_at": "2099-02-02T00:00:00Z",
                "assets": [{"name": "latest.json"}],
            },
            signed,
        ]
        selected = MODULE.select_signed_release(releases)
        self.assertEqual(selected["tag_name"], "v2099.1.1")
        self.assertIs(MODULE.select_signed_release(releases, "v2099.1.1"), signed)
        with self.assertRaisesRegex(SystemExit, "not a published signed release"):
            MODULE.select_signed_release(releases, "unsigned-v2099.1.2-r3")

    def test_metadata_validation_preserves_signed_source_urls(self):
        release = self.signed_release()
        metadata = self.metadata()
        MODULE.validate_metadata(
            metadata,
            repo="POf-L/Fanqie-novel-Downloader",
            source_tag="v2099.1.1",
            source_release=release,
        )
        metadata["platforms"]["windows-x86_64-nsis"]["url"] = metadata["platforms"][
            "windows-x86_64-nsis"
        ]["url"].replace("/v2099.1.1/", "/stable/")
        with self.assertRaisesRegex(SystemExit, "does not point"):
            MODULE.validate_metadata(
                metadata,
                repo="POf-L/Fanqie-novel-Downloader",
                source_tag="v2099.1.1",
                source_release=release,
            )

    def test_alias_payload_is_prerelease_and_never_latest(self):
        captured = []

        def fake_gh_json(arguments, *, input_text=None):
            captured.append((arguments, json.loads(input_text) if input_text else None))
            return {"id": 100, "tag_name": "stable"}

        with (
            patch.object(MODULE, "release_by_tag", return_value=None),
            patch.object(MODULE, "gh_json", side_effect=fake_gh_json),
        ):
            alias = MODULE.upsert_alias(
                repo="POf-L/Fanqie-novel-Downloader",
                alias_tag="stable",
                source_release=self.signed_release(),
            )

        self.assertEqual(alias["tag_name"], "stable")
        payload = captured[0][1]
        self.assertEqual(payload["prerelease"], True)
        self.assertEqual(payload["make_latest"], "false")
        self.assertEqual(payload["draft"], False)
        self.assertEqual(
            payload["target_commitish"],
            "0123456789abcdef0123456789abcdef01234567",
        )

    def test_endpoint_url_uses_alias_only_for_metadata(self):
        self.assertEqual(
            MODULE.source_metadata_url(
                "POf-L/Fanqie-novel-Downloader", "v2099.1.1"
            ),
            "https://github.com/POf-L/Fanqie-novel-Downloader/releases/download/v2099.1.1/latest.json",
        )

    def test_metadata_validation_decodes_asset_names(self):
        release = self.signed_release()
        release["assets"][2] = {
            "name": "FanqieNovelDownloader-tauri-windows-x64-setup.exe",
            "browser_download_url": (
                "https://github.com/POf-L/Fanqie-novel-Downloader/releases/download/"
                "v2099.1.1/FanqieNovelDownloader-tauri-windows-x64-setup.exe"
            ),
        }
        metadata = self.metadata()
        metadata["platforms"]["windows-x86_64-nsis"]["url"] = release["assets"][2][
            "browser_download_url"
        ]
        MODULE.validate_metadata(
            metadata,
            repo="POf-L/Fanqie-novel-Downloader",
            source_tag="v2099.1.1",
            source_release=release,
        )

    def test_metadata_validation_rejects_generic_and_cross_shape_entries(self):
        release = self.signed_release()
        metadata = self.metadata()
        metadata["platforms"]["windows-x86_64"] = metadata["platforms"].pop(
            "windows-x86_64-nsis"
        )
        with self.assertRaisesRegex(SystemExit, "generic or unsupported"):
            MODULE.validate_metadata(
                metadata,
                repo="POf-L/Fanqie-novel-Downloader",
                source_tag="v2099.1.1",
                source_release=release,
            )

        metadata = self.metadata()
        metadata["platforms"]["windows-x86_64-portable"] = metadata[
            "platforms"
        ].pop("windows-x86_64-nsis")
        with self.assertRaisesRegex(SystemExit, "does not match its asset"):
            MODULE.validate_metadata(
                metadata,
                repo="POf-L/Fanqie-novel-Downloader",
                source_tag="v2099.1.1",
                source_release=release,
            )

    def test_refresh_removes_non_metadata_alias_assets(self):
        alias = {
            "assets": [
                {"id": 41, "name": "latest.json"},
                {"id": 42, "name": "old-installer.exe"},
                {"id": 43, "name": "notes.txt"},
            ]
        }
        with patch.object(MODULE, "run") as mocked_run:
            MODULE.remove_non_metadata_assets(
                repo="POf-L/Fanqie-novel-Downloader", alias=alias
            )
        self.assertEqual(
            mocked_run.call_args_list,
            [
                call(
                    [
                        "gh",
                        "api",
                        "--method",
                        "DELETE",
                        "repos/POf-L/Fanqie-novel-Downloader/releases/assets/42",
                    ]
                ),
                call(
                    [
                        "gh",
                        "api",
                        "--method",
                        "DELETE",
                        "repos/POf-L/Fanqie-novel-Downloader/releases/assets/43",
                    ]
                ),
            ],
        )

    def test_public_metadata_verification_retries_cdn_delay(self):
        class Response:
            status = 200

            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        expected = self.metadata()
        with (
            patch.object(
                MODULE.urllib.request,
                "urlopen",
                side_effect=[OSError("CDN not ready"), Response(expected)],
            ) as urlopen,
            patch.object(MODULE.time, "sleep") as sleep,
        ):
            downloaded = MODULE.download_public_metadata(
                url="https://example.invalid/latest.json",
                expected=expected,
                attempts=2,
                delay_seconds=0.01,
            )
        self.assertEqual(downloaded, expected)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0.01)

    def test_refresh_requires_github_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(SystemExit, "GH_TOKEN"):
                    MODULE.refresh_stable_channel(
                        repo="POf-L/Fanqie-novel-Downloader",
                        work_dir=Path(directory),
                    )


if __name__ == "__main__":
    unittest.main()
