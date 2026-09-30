import asyncio
import json

import httpx
from config import TOKEN, API_URL

from bot.handlers import router
import scheduler.schedule as scheduler
import scheduler.scheduler_parser as scheduler_parser
from pathlib import Path
from scheduler.build_fgs_runtime import build_fgs_from_jsons

sched = scheduler.Scheduler()
folder = Path("scheduler/jsons")
FGS = {}


USERS_PATH = "users/users.json"

USER_STATE = {}
USER_SELECTION = {}

if not TOKEN:
    raise ValueError("MAX_TOKEN не найден. Проверь файл .env")


def load_users():
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_users(users):
    with open(USERS_PATH, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=2)


USERS = load_users()


async def get_updates(marker=None):
    url = f"{API_URL}/updates"

    headers = {
        "Authorization": TOKEN
    }

    params = {
        "limit": 100,
        "timeout": 30
    }

    if marker:
        params["marker"] = marker

    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.get(
            url,
            headers=headers,
            params=params
        )

    return response.json()


async def handle_update(update: dict):
    
    # print(json.dumps(update, indent=2, ensure_ascii=False))

    context = {
        "USERS": USERS,
        "USER_STATE": USER_STATE,
        "USER_SELECTION": USER_SELECTION,
        "save_users": save_users,
        "sched": sched,
        "FGS": FGS
    }

    await router.dispatch(update, context)
import traceback

async def main():
    marker = None

    print("Бот запущен")

    for file_path in folder.glob("*.json"):
        try:

            with open(file_path, encoding="utf-8") as file:

                parsed = scheduler_parser.parse_json(
                    file.read()
                )

                sched.parse_group(parsed)

            # print(f"Загружен: {file_path.name}")

        except Exception as e:

            print(f"Не загружен: {file_path.name}")
            print(e)
    global FGS
    FGS = build_fgs_from_jsons(
        excel_path="scheduler/МАХ-Профили_актуальные-26-27 у.г..xlsx",
        json_dir="scheduler/jsons"
    )
    print(FGS)
    
    print("FGS собран")

    while True:
        try:
            data = await get_updates(marker)
            updates = data.get("updates", [])

            for update in updates:
                marker = update.get("marker")
                await handle_update(update)

        except Exception as e:
            print("Ошибка:", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
