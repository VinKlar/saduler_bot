from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import  Optional

week_days : dict[str, int] = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}


def academic_year_start(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 8 else today.year - 1


def parse_academic_date(value: str) -> date:
    parts = value.split(".")
    day = int(parts[0])
    month = int(parts[1])
    start_year = academic_year_start()
    year = start_year if month >= 8 else start_year + 1
    return date(year, month, day)


class Meta (BaseModel): 
    group: str

class Period(BaseModel):
    start: date = Field(alias = "from")
    end: date = Field(alias = "to")

    @field_validator("start", "end", mode="before")
    @classmethod
    def convert_date(cls, value: str):
        return parse_academic_date(value)

class SubjectPeriods(BaseModel):
    lecture: Optional[Period] = None
    practice: Optional[Period] = None

class ClassRoom(BaseModel):
    room: str
    on_date: Optional[date] = Field(default=None, alias="date")
    start: Optional[date] = Field(default=None, alias="from")
    end: Optional[date] = Field(default=None, alias="until")

    @field_validator("on_date", "start", "end", mode="before")
    @classmethod
    def convert_date(cls, value: str | None):
        return parse_academic_date(value) if value else None

class Lesson(BaseModel):
    type: str
    group: Optional[str] = None
    groups: list[str] = Field(default_factory=list)
    subgroup: Optional[str] = None
    classroom: list[ClassRoom]

class Teacher(BaseModel):
    name: str
    groups: str = ""

class Subject(BaseModel):
    name: str
    period: SubjectPeriods
    nchet: dict[int, dict[int, list[Lesson]]] = Field(default_factory=dict)
    chet: dict[int, dict[int, list[Lesson]]] = Field(default_factory=dict)
    teachers: list[Teacher]

    @field_validator("chet", "nchet", mode="before")
    @classmethod
    def convert_week(cls, value):
        if value is None:
            return {}

        days_dict: dict[int, dict[int, list[Lesson]]] = {}

        for day, inner in value.items():
            lesson_dict: dict[int, list[Lesson]] = {}

            for par, lesson in inner.items():
                # Поддерживаем как прежний одиночный объект занятия, так и
                # несколько занятий, проходящих одновременно на одной паре.
                lesson_dict[int(par[4:])] = lesson if isinstance(lesson, list) else [lesson]

            days_dict[week_days[day]] = lesson_dict

        return days_dict

class GroupSchedule(BaseModel):
    meta: Meta
    subjects: list[Subject]

def parse_json(json: str):
    return GroupSchedule.model_validate_json(json)

# if __name__ == "__main__":
#     with open("test.json", encoding="utf-8") as file:
#         parsed = parse_json(file.read())
#         print(parsed.subjects[3].period.lecture)
