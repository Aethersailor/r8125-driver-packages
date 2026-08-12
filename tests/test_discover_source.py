import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "discover-source.py"
SPEC = importlib.util.spec_from_file_location("discover_source", SCRIPT_PATH)
assert SPEC and SPEC.loader
discover_source = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = discover_source
SPEC.loader.exec_module(discover_source)


def source_asset(source: str, version: str) -> discover_source.SourceAsset:
    return discover_source.SourceAsset(
        source=source,
        repo=f"example/{source}",
        release_tag=version,
        release_url=f"https://example.invalid/{source}/{version}",
        version=version,
        asset_name=f"r8125-{version}.tar.bz2",
        asset_url=f"https://example.invalid/{source}/r8125-{version}.tar.bz2",
        digest=f"sha256:{'a' * 64}",
        prerelease=False,
    )


class OfficialReleaseTests(unittest.TestCase):
    def test_parses_latest_r8125_archive(self) -> None:
        payload = {
            "Pass": True,
            "Data": {
                "DownloadItems": {
                    "Unix (Linux)": [
                        {
                            "DownloadId": "1",
                            "Name": "r8125-9.016.01.tar.bz2",
                            "Version": "9.016.01",
                            "UpdateTime": "2025/07/28",
                        },
                        {
                            "DownloadId": "2",
                            "Name": "r8125-9.018.00.tar.bz2",
                            "Version": "9.018.00",
                            "UpdateTime": "2026/07/03",
                        },
                        {
                            "DownloadId": "3",
                            "Name": "r8126-10.018.00.tar.bz2",
                            "Version": "10.018.00",
                            "UpdateTime": "2026/07/16",
                        },
                    ]
                }
            }
        }

        release = discover_source.parse_official_release(payload)

        self.assertEqual(release.version, "9.018.00")
        self.assertEqual(release.asset_name, "r8125-9.018.00.tar.bz2")
        self.assertEqual(release.download_id, "2")

    def test_rejects_missing_download_items(self) -> None:
        with self.assertRaisesRegex(ValueError, "DownloadItems"):
            discover_source.parse_official_release({"Pass": True, "Data": {}})

    def test_rejects_unsuccessful_response(self) -> None:
        with self.assertRaisesRegex(ValueError, "did not report success"):
            discover_source.parse_official_release({"Pass": False, "Data": {}})


class CandidateSelectionTests(unittest.TestCase):
    def test_ignores_version_newer_than_realtek(self) -> None:
        selected = discover_source.select_latest_candidate(
            [source_asset("untrusted", "99.001.00"), source_asset("mirror", "9.018.00")],
            "9.018.00",
        )

        self.assertEqual(selected.source, "mirror")

    def test_selects_newer_fallback_mirror(self) -> None:
        selected = discover_source.select_latest_candidate(
            [source_asset("openwrt", "9.016.01"), source_asset("danixland", "9.018.00")],
            "9.018.00",
        )

        self.assertEqual(selected.source, "danixland")

    def test_prefers_first_configured_source_for_equal_version(self) -> None:
        selected = discover_source.select_latest_candidate(
            [source_asset("openwrt", "9.018.00"), source_asset("danixland", "9.018.00")],
            "9.018.00",
        )

        self.assertEqual(selected.source, "openwrt")

    def test_requires_candidate_at_or_below_official_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "no mirrored source"):
            discover_source.select_latest_candidate(
                [source_asset("untrusted", "99.001.00")],
                "9.018.00",
            )


class SourceConfigurationTests(unittest.TestCase):
    def test_repository_configuration_contains_both_mirrors(self) -> None:
        config_path = Path(__file__).parents[1] / "config" / "sources.yml"

        sources = discover_source.parse_sources(str(config_path))

        self.assertEqual(
            [(item["name"], item["repo"]) for item in sources],
            [("openwrt", "openwrt/rtl8125"), ("danixland", "danixland/r8125")],
        )


class GitHubAssetTests(unittest.TestCase):
    def test_requires_github_sha256_digest(self) -> None:
        releases = [
            {
                "draft": False,
                "prerelease": False,
                "tag_name": "9.018.00",
                "html_url": "https://example.invalid/release",
                "assets": [
                    {
                        "name": "r8125-9.018.00.tar.bz2",
                        "browser_download_url": "https://example.invalid/source",
                        "digest": None,
                    }
                ],
            }
        ]
        original_github_json = discover_source.github_json
        discover_source.github_json = lambda _url: releases
        try:
            candidates = discover_source.candidates_for_source(
                {
                    "name": "mirror",
                    "repo": "example/mirror",
                    "asset_pattern": r"r8125-[0-9][0-9.]*\.tar\.bz2$",
                }
            )
        finally:
            discover_source.github_json = original_github_json

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
