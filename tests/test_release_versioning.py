import unittest

from updater import _parse_release_version


class ReleaseVersionTests(unittest.TestCase):
    def test_plain_semver_release_tags(self):
        self.assertEqual(_parse_release_version("v1.0.0"), (1, 0, 0))
        self.assertEqual(_parse_release_version("v1.2.10"), (1, 2, 10))

    def test_development_tags_are_ignored(self):
        self.assertIsNone(_parse_release_version("v1.3.1-bt.1"))
        self.assertIsNone(_parse_release_version("v1.3.1-bt.2"))
        self.assertIsNone(_parse_release_version("1.0.0"))

    def test_malformed_tags_are_ignored(self):
        for tag in ("latest", "v1.0", "v1.0.0-rc.1", "v1.0.0-beta"):
            with self.subTest(tag=tag):
                self.assertIsNone(_parse_release_version(tag))


if __name__ == "__main__":
    unittest.main()
