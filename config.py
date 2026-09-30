import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("MAX_TOKEN")
API_URL = "https://platform-api.max.ru"

if not TOKEN:
    raise ValueError("MAX_TOKEN не найден")