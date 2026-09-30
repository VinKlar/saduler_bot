import copy
import json
import httpx
import asyncio

from config import TOKEN, API_URL
from bot.file_cache import get_cached_file, set_cached_file

with open("bot/scen.json", "r", encoding="utf-8") as file:
    SCEN = json.load(file)

import os
import httpx

from config import TOKEN, API_URL




async def upload_file(file_path: str):
    # 1. Получаем URL для загрузки
    url = f"{API_URL}/uploads"

    headers = {
        "Authorization": TOKEN
    }

    params = {
        "type": "file"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            params=params
        )

    print("GET UPLOAD URL:", response.status_code, response.text)

    if response.status_code != 200:
        raise Exception(f"Не удалось получить upload URL: {response.text}")

    upload_info = response.json()
    upload_url = upload_info["url"]

    # 2. Загружаем файл по полученному URL
    with open(file_path, "rb") as file:
        files = {
            "data": file
        }

        async with httpx.AsyncClient(timeout=120) as client:
            upload_response = await client.post(
                upload_url,
                files=files
            )

    print("UPLOAD FILE:", upload_response.status_code, upload_response.text)

    if upload_response.status_code != 200:
        raise Exception(f"Не удалось загрузить файл: {upload_response.text}")

    return upload_response.json()

async def get_or_upload_file(file_path: str):
    cached = get_cached_file(file_path)

    if cached:
        print("FILE CACHE HIT:", file_path)
        return cached

    print("FILE CACHE MISS:", file_path)

    upload_result = await upload_file(file_path)

    await asyncio.sleep(3)

    set_cached_file(file_path, upload_result)

    return upload_result


async def send_file(
    chat_id: int,
    file_path: str,
    text: str = "Файл"
):
    upload_result = await get_or_upload_file(file_path)

    url = f"{API_URL}/messages"

    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    params = {
        "chat_id": chat_id
    }

    json_data = {
        "text": text,
        "attachments": [
            {
                "type": "file",
                "payload": upload_result
            }
        ]
    }

    tmp_scen = copy.deepcopy(SCEN["push_button"])
    keyboard = await create_keyboard(tmp_scen["buttons"])

    json_data["attachments"].extend(
        keyboard["attachments"]
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            params=params,
            json=json_data
        )

    print("SEND FILE:", response.status_code)
    print("SEND FILE:", response.text)

    return response.json()

async def send_message(chat_id: int, scen, **data):
    url = f"{API_URL}/messages"

    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    params = {
        "chat_id": chat_id
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            params=params,
            json=await scen_worker(scen, **data)
        )

async def create_keyboard(buttons):
    return {
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": buttons
                }
            }
        ]
    }
    
async def scen_worker(scen, **data):
    tmp_scen = copy.deepcopy(SCEN[scen])
    tmp_scen['text'] = tmp_scen['text'].format(text=data.get('text'))

    if data.get("buttons") is not None:
        tmp_scen["buttons"] = data["buttons"]

    if tmp_scen.get('buttons'):
        data_respons = {
            "text": tmp_scen['text'],
            **await create_keyboard(tmp_scen['buttons'])
        }
    else:
        data_respons = {
            "text": tmp_scen['text']
        }
    
    return data_respons
