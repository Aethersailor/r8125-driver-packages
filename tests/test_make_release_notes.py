import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "make-release-notes.py"
SPEC = importlib.util.spec_from_file_location("make_release_notes", SCRIPT_PATH)
assert SPEC and SPEC.loader
make_release_notes = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = make_release_notes
SPEC.loader.exec_module(make_release_notes)


METADATA = {
    "driver_version": "9.018.00",
    "official_driver_version": "9.018.00",
    "source": "danixland",
    "repo": "danixland/r8125",
    "asset_name": "r8125-9.018.00.tar.bz2",
    "source_sha256": "a" * 64,
}


class ReleaseNotesTests(unittest.TestCase):
    def test_highlights_installable_package_and_explains_assets(self) -> None:
        notes = make_release_notes.render_release_notes(
            METADATA,
            "9.018.00-1",
            "Aethersailor/r8125-driver-packages",
            ["CONFIG_ASPM=n", "ENABLE_EEE=n"],
        )

        package_url = (
            "https://github.com/Aethersailor/r8125-driver-packages/releases/download/"
            "v9.018.00-1/r8125-dkms_9.018.00-1_all.deb"
        )
        self.assertIn(f"[`r8125-dkms_9.018.00-1_all.deb`]({package_url})", notes)
        self.assertIn("sudo apt install ./r8125-dkms_9.018.00-1_all.deb", notes)
        self.assertIn("`provenance.json`", notes)
        self.assertIn("安装是否需要", notes)
        self.assertIn("`Source code (zip)`", notes)
        self.assertIn("not DKMS packages", notes)

    def test_rejects_invalid_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid GitHub repository"):
            make_release_notes.render_release_notes(
                METADATA,
                "9.018.00-1",
                "invalid repository",
                [],
            )

    def test_rejects_invalid_package_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid package version"):
            make_release_notes.render_release_notes(
                METADATA,
                "latest",
                "Aethersailor/r8125-driver-packages",
                [],
            )


if __name__ == "__main__":
    unittest.main()
