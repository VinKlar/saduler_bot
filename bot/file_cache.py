import json
from datetime import date
from pathlib import Path
from datetime import date

CACHE_PATH = Path("cache/file_tokens.json")

def current_month():
    return date.today().strftime("%Y-%m")

def load_cache():
    if not CACHE_PATH.exists():
        return {}

    with open(CACHE_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def save_cache(cache):
    CACHE_PATH.parent.mkdir(exist_ok=True)

    with open(CACHE_PATH, "w", encoding="utf-8") as file:
        json.dump(cache, file, ensure_ascii=False, indent=2)


def get_cached_file(file_key: str):
    cache = load_cache()
    item = cache.get(file_key)

    if not item:
        return None

    if item.get("month") != current_month():
        return None

    return item.get("upload_result")


def set_cached_file(file_key: str, upload_result: dict):
    cache = load_cache()

    cache[file_key] = {
        "month": current_month(),
        "upload_result": upload_result
    }

    save_cache(cache)