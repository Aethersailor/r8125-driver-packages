#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from release_plan import ExistingRelease, choose_release  # noqa: E402


SOURCE_A = "a" * 64
SOURCE_B = "b" * 64


class ChooseReleaseTests(unittest.TestCase):
    def test_new_driver_starts_at_revision_one(self) -> None:
        decision = choose_release("9.017.00", SOURCE_A, [])
        self.assertTrue(decision.should_release)
        self.assertFalse(decision.replace_existing)
        self.assertEqual(decision.tag, "v9.017.00-1")
        self.assertEqual(decision.reason, "new-driver-version")

    def test_unchanged_source_and_recipe_skip_latest_release(self) -> None:
        releases = [ExistingRelease(2, "v9.016.01-2", "abc", SOURCE_A)]
        decision = choose_release("9.016.01", SOURCE_A, releases)
        self.assertFalse(decision.should_release)
        self.assertEqual(decision.pkgrel, 2)
        self.assertEqual(decision.reason, "source-and-package-recipe-unchanged")

    def test_recipe_change_increments_latest_revision(self) -> None:
        releases = [
            ExistingRelease(1, "v9.016.01-1", "abc", SOURCE_A),
            ExistingRelease(3, "v9.016.01-3", "def", SOURCE_A),
        ]
        decision = choose_release(
            "9.016.01",
            SOURCE_A,
            releases,
            has_recipe_changes=True,
        )
        self.assertTrue(decision.should_release)
        self.assertEqual(decision.tag, "v9.016.01-4")
        self.assertEqual(decision.reason, "package-recipe-changed")

    def test_replaced_source_asset_increments_revision(self) -> None:
        releases = [ExistingRelease(2, "v9.016.01-2", "abc", SOURCE_A)]
        decision = choose_release("9.016.01", SOURCE_B, releases)
        self.assertTrue(decision.should_release)
        self.assertEqual(decision.tag, "v9.016.01-3")
        self.assertEqual(decision.reason, "source-asset-changed")

    def test_manual_existing_revision_is_skipped_without_force(self) -> None:
        releases = [ExistingRelease(2, "v9.016.01-2", "abc", None)]
        decision = choose_release(
            "9.016.01",
            SOURCE_A,
            releases,
            manual_pkgrel="2",
        )
        self.assertFalse(decision.should_release)
        self.assertFalse(decision.replace_existing)
        self.assertEqual(decision.reason, "manual-tag-already-exists")

    def test_manual_new_revision_is_published(self) -> None:
        releases = [ExistingRelease(2, "v9.016.01-2", "abc", None)]
        decision = choose_release(
            "9.016.01",
            SOURCE_A,
            releases,
            manual_pkgrel="5",
        )
        self.assertTrue(decision.should_release)
        self.assertFalse(decision.replace_existing)
        self.assertEqual(decision.tag, "v9.016.01-5")

    def test_force_without_revision_rebuilds_latest_release(self) -> None:
        releases = [ExistingRelease(2, "v9.016.01-2", "abc", None)]
        decision = choose_release("9.016.01", SOURCE_A, releases, force=True)
        self.assertTrue(decision.should_release)
        self.assertTrue(decision.replace_existing)
        self.assertEqual(decision.tag, "v9.016.01-2")
        self.assertEqual(decision.reason, "forced-rebuild")

    def test_invalid_manual_revision_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            choose_release("9.016.01", SOURCE_A, [], manual_pkgrel="0")


if __name__ == "__main__":
    unittest.main()
