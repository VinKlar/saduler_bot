import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


def create_backup(source: Path, backup_dir: Path, keep: int = 50) -> Path:
    if keep < 1:
        raise ValueError("Количество сохраняемых копий должно быть больше нуля")

    with source.open("r", encoding="utf-8") as file:
        users = json.load(file)

    if not isinstance(users, dict):
        raise ValueError("users.json должен содержать JSON-объект")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    destination = backup_dir / f"users_{timestamp}.json"
    shutil.copy2(source, destination)

    backups = sorted(
        backup_dir.glob("users_*.json"),
        key=lambda path: path.name,
        reverse=True,
    )
    for old_backup in backups[keep:]:
        old_backup.unlink()

    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Создать резервную копию users.json")
    parser.add_argument("source", type=Path)
    parser.add_argument("backup_dir", type=Path)
    parser.add_argument("--keep", type=int, default=50)
    args = parser.parse_args()

    try:
        destination = create_backup(args.source, args.backup_dir, args.keep)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Не удалось создать резервную копию пользователей: {error}")
        return 1

    print(f"Создана резервная копия пользователей: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
