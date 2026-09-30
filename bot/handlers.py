from bot.router import Router
from bot.conveyor import send_message, send_file
from datetime import date
from datetime import datetime, timedelta
from datetime import date
from bot.calendar_keyboard import create_calendar_buttons
from bot.group_catalog import GROUP_CATALOG


router = Router()

SEARCH_PROMPT = (
    "Введите код и наименование направления, например:\n"
    "09.03.03 Прикладная информатика\n\n"
    "Если знаете номер группы, введите его сразу, например: 8101"
)

WELCOME_TEXT = (
    "Добро пожаловать в бот расписания Университета биотехнологий!\n\n"
    "Бот поможет быстро узнать занятия на сегодня, завтра или выбранную дату. "
    "Расписание учитывает вашу группу и подгруппу.\n\n"
    "Как начать:\n"
    "1. Введите направление обучения или номер группы.\n"
    "2. Выберите профиль, группу и подгруппу.\n"
    "3. Используйте кнопки «Сегодня», «Завтра» или «Выбрать дату».\n\n"
    "Позже изменить направление, группу или подгруппу можно через кнопку «Меню».\n\n"
    + SEARCH_PROMPT
)


def make_button_rows(items, text_factory, payload_factory, per_row=2):
    buttons = [
        {
            "type": "callback",
            "text": text_factory(item)[:100],
            "payload": payload_factory(item),
        }
        for item in items
    ]
    return [buttons[index:index + per_row] for index in range(0, len(buttons), per_row)]


async def begin_group_selection(event, context, text=SEARCH_PROMPT):
    context["USER_SELECTION"].pop(event.user_id, None)
    context["USER_STATE"][event.user_id] = "WAIT_SEARCH"
    await send_message(event.chat_id, "selection", text=text)


def get_available_subgroups(context, group: str) -> list[str]:
    schedule_group = context.get("FGS", {}).get(group)
    sched = context.get("sched")
    if not schedule_group or sched is None:
        return []
    return sched.get_subgroups(schedule_group, group)


async def show_subgroups(event, context, group_info, subgroups):
    context["USER_STATE"][event.user_id] = "WAIT_SUBGROUP"
    context["USER_SELECTION"][event.user_id] = {
        "group_info": group_info,
        "subgroups": subgroups,
    }
    buttons = make_button_rows(
        subgroups,
        lambda subgroup: f"Подгруппа {subgroup}",
        lambda subgroup: f"subgroup:{subgroup}",
    )
    await send_message(
        event.chat_id,
        "selection",
        text=f"Группа {group_info['group']}\n\nВыберите подгруппу:",
        buttons=buttons,
    )


async def finish_group_selection(event, context, group_info, subgroup=None):
    user_key = str(event.user_id)
    user = {"group": group_info["group"]}
    if subgroup is not None:
        user["subgroup"] = subgroup
    context["USERS"][user_key] = user
    context["save_users"](context["USERS"])
    context["USER_STATE"].pop(event.user_id, None)
    context["USER_SELECTION"].pop(event.user_id, None)

    await send_message(
        event.chat_id,
        "push_button",
        text=(
            f"Группа сохранена: {group_info['group']}\n"
            f"Направление: {group_info['direction_code']} "
            f"{group_info['direction_name']}\n"
            f"Профиль: {group_info['profile']}\n"
            f"Форма обучения: {group_info['study_form']}"
            + (f"\nПодгруппа: {subgroup}" if subgroup is not None else "")
        ),
    )


async def save_group(event, context, group_info):
    subgroups = get_available_subgroups(context, group_info["group"])
    if len(subgroups) > 1:
        await show_subgroups(event, context, group_info, subgroups)
        return

    subgroup = subgroups[0] if subgroups else None
    await finish_group_selection(event, context, group_info, subgroup)


async def show_directions(event, context, directions):
    context["USER_STATE"][event.user_id] = "WAIT_DIRECTION"
    context["USER_SELECTION"][event.user_id] = {
        "direction_ids": [item["id"] for item in directions]
    }
    buttons = make_button_rows(
        directions,
        lambda item: f"{item['code']} {item['name']}",
        lambda item: f"direction:{item['id']}",
        per_row=1,
    )
    await send_message(
        event.chat_id,
        "selection",
        text="Найдено несколько направлений. Выберите нужное:",
        buttons=buttons,
    )


async def show_profiles(event, context, direction):
    context["USER_STATE"][event.user_id] = "WAIT_PROFILE"
    context["USER_SELECTION"][event.user_id] = {
        "direction_id": direction["id"]
    }
    buttons = make_button_rows(
        direction["profiles"],
        lambda item: f"{item['name']} — {item['study_form']}",
        lambda item: f"profile:{direction['id']}:{item['id']}",
        per_row=1,
    )
    await send_message(
        event.chat_id,
        "selection",
        text=f"{direction['code']} {direction['name']}\n\nВыберите профиль и форму обучения:",
        buttons=buttons,
    )


async def show_groups(event, context, direction, profile):
    context["USER_STATE"][event.user_id] = "WAIT_GROUP"
    context["USER_SELECTION"][event.user_id] = {
        "direction_id": direction["id"],
        "profile_id": profile["id"],
    }
    buttons = make_button_rows(
        profile["groups"],
        lambda group: group,
        lambda group: f"group:{group}",
    )
    await send_message(
        event.chat_id,
        "selection",
        text=(
            f"Профиль: {profile['name']}\n"
            f"Форма обучения: {profile['study_form']}\n\n"
            "Выберите группу:"
        ),
        buttons=buttons,
    )


def get_selected_schedule_group(event, context):
    user = context["USERS"].get(str(event.user_id), {})
    selected_group = user.get("group")
    subgroup = user.get("subgroup")
    return selected_group, context["FGS"].get(selected_group), subgroup


async def send_schedule_unavailable(event, selected_group):
    await send_message(
        event.chat_id,
        "push_button",
        text=f"Расписание для группы {selected_group or 'не выбрана'} пока не загружено.",
    )


def format_lesson(item):
    lesson_type = "Лекция" if item.is_lecture() else item.type
    teacher = item.subject.teacher or "не указан"
    return (
        f"  {item.subject.name} ({item.cabinet}) — {lesson_type}\n"
        f"  Преподаватель: {teacher}"
    )

@router.bot_started()
async def start_handler(event, context):
    user_key = str(event.user_id)

    if context["USERS"].get(user_key) is None:
        await begin_group_selection(event, context, WELCOME_TEXT)
        return

    await send_message(
        event.chat_id,
        "/start"
    )
    
@router.command("re_group")
async def re_group_handler(event, context):

    user_key = str(event.user_id)

    # удаляем старую группу
    if user_key in context["USERS"]:
        del context["USERS"][user_key]

    # сохраняем users.json
    context["save_users"](context["USERS"])

    await begin_group_selection(event, context)

@router.message("/start")
async def start_handler(event, context):
    user_key = str(event.user_id)

    if context["USERS"].get(user_key) is None:
        await begin_group_selection(event, context, WELCOME_TEXT)
        return

    await send_message(
        event.chat_id,
        "/start"
    )

@router.state("WAIT_SEARCH")
async def wait_search_handler(event, context):
    if event.type != "message":
        await send_message(event.chat_id, "selection", text=SEARCH_PROMPT)
        return

    group_info = GROUP_CATALOG.find_group(event.text)
    if group_info:
        await save_group(event, context, group_info)
        return

    directions = GROUP_CATALOG.search_directions(event.text)
    if len(directions) == 1:
        await show_profiles(event, context, directions[0])
        return
    if len(directions) > 1:
        await show_directions(event, context, directions)
        return

    await send_message(
        event.chat_id,
        "selection",
        text=f"Ничего не найдено.\n\n{SEARCH_PROMPT}",
    )


@router.state("WAIT_DIRECTION")
async def wait_direction_handler(event, context):
    if event.type != "callback" or not (event.payload or "").startswith("direction:"):
        await begin_group_selection(event, context, "Введите направление заново.\n\n" + SEARCH_PROMPT)
        return

    direction_id = event.payload.split(":", 1)[1]
    allowed_ids = context["USER_SELECTION"].get(event.user_id, {}).get("direction_ids", [])
    direction = GROUP_CATALOG.get_direction(direction_id)
    if not direction or direction_id not in allowed_ids:
        await begin_group_selection(event, context, "Направление устарело.\n\n" + SEARCH_PROMPT)
        return

    await show_profiles(event, context, direction)


@router.state("WAIT_PROFILE")
async def wait_profile_handler(event, context):
    payload = event.payload or ""
    if event.type != "callback" or not payload.startswith("profile:"):
        await send_message(event.chat_id, "selection", text="Выберите профиль кнопкой выше.")
        return

    _, direction_id, profile_id = payload.split(":", 2)
    selected_direction = context["USER_SELECTION"].get(event.user_id, {}).get("direction_id")
    direction = GROUP_CATALOG.get_direction(direction_id)
    profile = GROUP_CATALOG.get_profile(direction_id, profile_id)
    if not direction or not profile or direction_id != selected_direction:
        await begin_group_selection(event, context, "Выбор устарел.\n\n" + SEARCH_PROMPT)
        return

    await show_groups(event, context, direction, profile)


@router.state("WAIT_GROUP")
async def wait_group_handler(event, context):
    if event.type == "message":
        group_info = GROUP_CATALOG.find_group(event.text)
    elif event.type == "callback" and (event.payload or "").startswith("group:"):
        group_info = GROUP_CATALOG.find_group(event.payload.split(":", 1)[1])
    else:
        group_info = None

    selection = context["USER_SELECTION"].get(event.user_id, {})
    profile = GROUP_CATALOG.get_profile(
        selection.get("direction_id", ""),
        selection.get("profile_id", ""),
    )

    if not group_info or not profile or group_info["group"] not in profile["groups"]:
        await send_message(event.chat_id, "selection", text="Выберите группу кнопкой выше.")
        return

    await save_group(event, context, group_info)


@router.state("WAIT_SUBGROUP")
async def wait_subgroup_handler(event, context):
    payload = event.payload or ""
    selection = context["USER_SELECTION"].get(event.user_id, {})
    allowed_subgroups = selection.get("subgroups", [])

    if event.type != "callback" or not payload.startswith("subgroup:"):
        await send_message(event.chat_id, "selection", text="Выберите подгруппу кнопкой выше.")
        return

    subgroup = payload.split(":", 1)[1]
    group_info = selection.get("group_info")
    if subgroup not in allowed_subgroups or not group_info:
        await begin_group_selection(event, context, "Выбор устарел. Выберите группу заново.")
        return

    await finish_group_selection(event, context, group_info, subgroup)


@router.callback("settings")
async def settings_handler(event, context):
    user = context["USERS"].get(str(event.user_id), {})
    group = user.get("group", "не выбрана")
    subgroup = user.get("subgroup", "не выбрана")
    buttons = [
        [
            {"type": "callback", "text": "Сменить подгруппу", "payload": "settings_subgroup"},
        ],
        [
            {"type": "callback", "text": "Сменить группу", "payload": "settings_group"},
        ],
        [
            {"type": "callback", "text": "Сменить направление", "payload": "settings_direction"},
        ],
    ]
    await send_message(
        event.chat_id,
        "selection",
        text=f"Настройки расписания\n\nГруппа: {group}\nПодгруппа: {subgroup}",
        buttons=buttons,
    )


@router.callback("settings_subgroup")
async def settings_subgroup_handler(event, context):
    user = context["USERS"].get(str(event.user_id), {})
    group_info = GROUP_CATALOG.find_group(user.get("group", ""))
    if not group_info:
        await begin_group_selection(event, context)
        return

    subgroups = get_available_subgroups(context, group_info["group"])
    if len(subgroups) < 2:
        await send_message(
            event.chat_id,
            "push_button",
            text="Для этой группы выбор подгруппы в расписании не предусмотрен.",
        )
        return

    await show_subgroups(event, context, group_info, subgroups)


@router.callback("settings_group")
async def settings_group_handler(event, context):
    user = context["USERS"].get(str(event.user_id), {})
    group_info = GROUP_CATALOG.find_group(user.get("group", ""))
    if not group_info:
        await begin_group_selection(event, context)
        return

    direction = GROUP_CATALOG.get_direction(group_info["direction_id"])
    profile = next(
        (
            item
            for item in direction["profiles"]
            if group_info["group"] in item["groups"]
        ),
        None,
    ) if direction else None
    if not direction or not profile:
        await begin_group_selection(event, context)
        return

    await show_groups(event, context, direction, profile)


@router.callback("settings_direction")
async def settings_direction_handler(event, context):
    await begin_group_selection(event, context)


@router.message("Сегодня")
async def today_handler(event, context):
    await send_message(
        event.chat_id,
        "push_button",
        text="Расписание на сегодня"
    )


@router.message("Завтра")
async def tomorrow_handler(event, context):
    await send_message(
        event.chat_id,
        "push_button",
        text="Расписание на завтра"
    )


@router.callback("today")
async def today_callback_handler(event, context):
    lesson_index = 0

    lines = []
    selected_group, schedule_group, subgroup = get_selected_schedule_group(event, context)
    if not schedule_group:
        await send_schedule_unavailable(event, selected_group)
        return

    for item in context['sched'].get_day(
        datetime.now().date(), schedule_group, selected_group, subgroup
    ):
        print(item)
        if lesson_index != item.index:
            lesson_index = item.index

            lines.append(f"{lesson_index} пара")

        lines.append(format_lesson(item))

    text = "\n".join(lines)
    if not text:
        text = "На эту дату занятий нет"
    else:
        text = f"Расписание на {datetime.now().date()}\n"+text

    await send_message(
        event.chat_id,
        "push_button",
        text=text
    )

@router.callback("all")
async def all_callback_handler(event, context):
    selected_group, schedule_group, _ = get_selected_schedule_group(event, context)
    if not schedule_group:
        await send_schedule_unavailable(event, selected_group)
        return

    await send_file(
        event.chat_id,
        f"scheduler/xls/{schedule_group}.xls",
        text="Общее расписание"
    )


@router.callback("tomorrow")
async def tomorrow_callback_handler(event, context):

    lesson_index = 0

    lines = []
    selected_group, schedule_group, subgroup = get_selected_schedule_group(event, context)
    if not schedule_group:
        await send_schedule_unavailable(event, selected_group)
        return

    for item in context['sched'].get_day(
        datetime.now().date() + timedelta(days=1),
        schedule_group,
        selected_group,
        subgroup,
    ):

        if lesson_index != item.index:
            lesson_index = item.index

            lines.append(f"{lesson_index} пара")

        lines.append(format_lesson(item))

    text = "\n".join(lines)
    if not text:
        text = "На эту дату занятий нет"
    else:
        text = f"Расписание на {datetime.now().date() + timedelta(days=1)}\n"+text

    await send_message(
        event.chat_id,
        "push_button",
        text=text
    )

@router.callback("select_date")
async def select_date_handler(event, context):
    context["USER_STATE"][event.user_id] = "WAIT_DATE"

    await send_message(
        event.chat_id,
        "select_date",
        text="Введите дату в формате ДД.ММ.ГГГГ\nНапример: 15.05.2026"
    )

@router.callback("cancel")
async def select_date_handler(event, context):
    context["USER_STATE"].pop(
        event.user_id,
        None
    )

    await send_message(
        event.chat_id,
        "push_button",
        text="Выберите действие: "
    )

@router.state("WAIT_DATE")
async def wait_date_handler(event, context):

    if event.type != "message":
        await send_message(
            event.chat_id,
            "select_date",
            text="Введите дату текстом в формате ДД.ММ.ГГГГ"
        )
        return

    try:
        selected_date = datetime.strptime(
            event.text,
            "%d.%m.%Y"
        ).date()

    except ValueError:
        await send_message(
            event.chat_id,
            "select_date",
            text="Неверный формат даты. Введите так: 15.05.2026"
        )
        return

    context["USER_STATE"].pop(event.user_id, None)

    lesson_index = 0
    lines = []

    selected_group, group, subgroup = get_selected_schedule_group(event, context)
    if not group:
        await send_schedule_unavailable(event, selected_group)
        return

    try:
        result = context["sched"].get_day(
            selected_date,
            group,
            selected_group,
            subgroup,
        )

    except Exception as e:
        print("Ошибка get_day:", e)
        result = []

    for item in result:

        if lesson_index != item.index:
            lesson_index = item.index
            lines.append(f"{lesson_index} пара")

        lines.append(format_lesson(item))

    text = "\n".join(lines)

    if not text:
        text = "На эту дату занятий нет"
    else:
        text = f"Расписание на {selected_date}\n"+text

    await send_message(
        event.chat_id,
        "push_button",
        text=text
    )

@router.callback()
async def callback_handler(event, context):
    payload = event.payload

    if payload == "ignore":
        return

    if payload.startswith("date:"):
        selected_date = payload.replace("date:", "")

        await send_message(
            event.chat_id,
            "push_button",
            text=f"Вы выбрали дату: {selected_date}"
        )
        return

@router.message()
async def unknown_message_handler(event, context):
    await send_message(
        event.chat_id,
        "push_button",
        text=f"Не понял сообщение: {event.text}"
    )


# @router.callback()
# async def unknown_callback_handler(event, context):
#     await send_message(
#         event.chat_id,
#         "push_button",
#         text=f"Неизвестная кнопка: {event.payload}"
#     )
