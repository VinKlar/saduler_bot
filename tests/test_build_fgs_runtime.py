import unittest

from scheduler.build_fgs_runtime import expand_filename_groups


class ExpandFilenameGroupsTests(unittest.TestCase):
    def test_expands_abbreviated_group_numbers(self):
        self.assertEqual(
            expand_filename_groups("8101,02,03"),
            ["8101", "8102", "8103"],
        )

    def test_keeps_full_group_numbers(self):
        self.assertEqual(
            expand_filename_groups("4161,4267"),
            ["4161", "4267"],
        )

    def test_keeps_single_group(self):
        self.assertEqual(expand_filename_groups("8101"), ["8101"])


if __name__ == "__main__":
    unittest.main()
