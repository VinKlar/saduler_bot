import calendar
from datetime import date


def create_calendar_buttons(year: int, month: int):
    cal = calendar.Calendar(firstweekday=0)

    buttons = [
        [
            {"type": "callback", "text": "Пн", "payload": "ignore"},
            {"type": "callback", "text": "Вт", "payload": "ignore"},
            {"type": "callback", "text": "Ср", "payload": "ignore"}
        ],
        [
            {"type": "callback", "text": "Чт", "payload": "ignore"},
            {"type": "callback", "text": "Пт", "payload": "ignore"},
            {"type": "callback", "text": "Сб", "payload": "ignore"}
        ]
    ]

    current_row = []

    for week in cal.monthdatescalendar(year, month):

        for day in week:

            if day.weekday() == 6:
                continue

            if day.month != month:
                button = {
                    "type": "callback",
                    "text": " ",
                    "payload": "ignore"
                }
            else:
                button = {
                    "type": "callback",
                    "text": str(day.day),
                    "payload": f"date:{day.isoformat()}"
                }

            current_row.append(button)

            if len(current_row) == 3:
                buttons.append(current_row)
                current_row = []

    if current_row:
        buttons.append(current_row)

    buttons.append([
        {
            "type": "callback",
            "text": "←",
            "payload": f"calendar_prev:{year}-{month:02d}"
        },
        {
            "type": "callback",
            "text": "Сегодня",
            "payload": f"date:{date.today().isoformat()}"
        },
        {
            "type": "callback",
            "text": "→",
            "payload": f"calendar_next:{year}-{month:02d}"
        }
    ])

    return buttons