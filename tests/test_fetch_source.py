import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "fetch-source.py"
SPEC = importlib.util.spec_from_file_location("fetch_source", SCRIPT_PATH)
assert SPEC and SPEC.loader
fetch_source = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fetch_source
SPEC.loader.exec_module(fetch_source)


class SourceDigestTests(unittest.TestCase):
    def test_accepts_prefixed_sha256(self) -> None:
        digest = "a" * 64
        self.assertEqual(fetch_source.normalize_sha256(f"sha256:{digest}"), digest)

    def test_accepts_bare_sha256(self) -> None:
        digest = "A" * 64
        self.assertEqual(fetch_source.normalize_sha256(digest), digest.lower())

    def test_rejects_missing_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid SHA256"):
            fetch_source.normalize_sha256("")

    def test_rejects_non_sha256_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid SHA256"):
            fetch_source.normalize_sha256("md5:" + "a" * 32)


if __name__ == "__main__":
    unittest.main()
