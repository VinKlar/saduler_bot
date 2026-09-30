import json
import tempfile
import unittest
from pathlib import Path

from backup_users import create_backup


class BackupUsersTests(unittest.TestCase):
    def test_creates_valid_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "users.json"
            source.write_text('{"1": {"group": "8101"}}', encoding="utf-8")

            destination = create_backup(source, root / "backups")

            self.assertTrue(destination.exists())
            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                {"1": {"group": "8101"}},
            )

    def test_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "users.json"
            source.write_text("", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                create_backup(source, root / "backups")

    def test_removes_old_backups_over_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "users.json"
            source.write_text("{}", encoding="utf-8")
            backup_dir = root / "backups"

            for index in range(3):
                (backup_dir / f"users_2000-01-01_00-00-00_00000{index}.json").parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                (backup_dir / f"users_2000-01-01_00-00-00_00000{index}.json").write_text(
                    "{}",
                    encoding="utf-8",
                )

            create_backup(source, backup_dir, keep=2)

            self.assertEqual(len(list(backup_dir.glob("users_*.json"))), 2)


if __name__ == "__main__":
    unittest.main()
