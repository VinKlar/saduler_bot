from datetime import date, timedelta
import scheduler.scheduler_parser as scheduler_parser


class DateRange:
    
    def __init__(self, start: date, end: date):
        if start > end:
           raise ValueError(f"Невалидный диапозон дат (start = {start} > end = {end})") 
        self.__start = start
        self.__end = end
    
    @staticmethod
    def make_from(period: scheduler_parser.Period | None):
        if period:
            return DateRange(period.start, period.end)
        else:
            start_year = scheduler_parser.academic_year_start()
            return DateRange(date(start_year, 8, 1), date(start_year + 1, 7, 31))

    def in_range(self, date: date):
        return self.__start <= date <= self.__end

class DayParser:
    
    def __init__(self, start: date, max_week: int = 100):
        self.start = start # Должен быть понедельником!
        self.max_week = max_week

    def make_index(self, week_day: int, even: bool):
        return int(even) * 7 + week_day

    def parse(self, day: date):
        week_number = (day - self.start).days // 7
        if week_number < self.max_week: 
            # Неделя, содержащая 1 сентября, является первой нечётной.
            # Нечётная неделя хранится в индексах 0-6, чётная — 7-13.
            return week_number % 2 * 7 + day.weekday()
        else:
            return None


class Subject:
    
    def __init__(self, name: str, teacher: str, lecture_range: DateRange, practice_range: DateRange):
        self.name = name
        self.teacher = teacher
        self.lecture_range = lecture_range
        self.practice_range = practice_range
    
    @staticmethod
    def make_from(subject: scheduler_parser.Subject):
        teacher = subject.teachers[0].name if subject.teachers else ""
        return Subject(
            subject.name, teacher,
            DateRange.make_from(subject.period.lecture), 
            DateRange.make_from(subject.period.practice)
        )

class Lesson:

    def __init__(
        self,
        index: int,
        subject: Subject,
        cabinet: str,
        type: str,
        classrooms=None,
        group: str | None = None,
        groups=None,
        subgroup: str | None = None,
    ):
        self.index = index
        self.subject = subject
        self.cabinet = cabinet
        self.type = type
        self.classrooms = classrooms or []
        self.group = group
        self.groups = groups or []
        self.subgroup = subgroup

    def is_lecture(self):
        return self.type == "Л"
    
    def check_period(self, day: date):
        if self.is_lecture():
            return self.subject.lecture_range.in_range(day)
        return self.subject.practice_range.in_range(day)

    @staticmethod
    def classroom_matches_day(classroom: scheduler_parser.ClassRoom, day: date):
        if classroom.on_date is not None:
            return day == classroom.on_date
        if classroom.start is not None and day < classroom.start:
            return False
        if classroom.end is not None and day > classroom.end:
            return False
        return True

    def matches_group(self, group: str | None):
        if self.group is not None and group != self.group:
            return False
        if self.groups and group not in self.groups:
            return False
        return True

    def matches_subgroup(self, subgroup: str | None):
        # Для старых пользователей без сохранённой подгруппы сохраняем прежнее
        # поведение и показываем все занятия. После выбора фильтр становится строгим.
        return subgroup is None or self.subgroup is None or subgroup == self.subgroup

    def for_day(self, day: date, group: str | None = None, subgroup: str | None = None):
        if (
            not self.check_period(day)
            or not self.matches_group(group)
            or not self.matches_subgroup(subgroup)
        ):
            return None

        classrooms = [
            classroom
            for classroom in self.classrooms
            if self.classroom_matches_day(classroom, day)
        ]
        if not classrooms:
            return None

        cabinet = ", ".join(room.room for room in classrooms)
        return Lesson(
            self.index,
            self.subject,
            cabinet or "аудитория не указана",
            self.type,
            classrooms,
            self.group,
            self.groups,
            self.subgroup,
        )
    
    @staticmethod
    def make_from(data: scheduler_parser.Lesson, index: int, subject: Subject):
        cabinet = ", ".join(room.room for room in data.classroom)
        return Lesson(
            index,
            subject,
            cabinet or "аудитория не указана",
            data.type,
            data.classroom,
            data.group,
            data.groups,
            data.subgroup,
        )

class LessonList:
    lessons : list[Lesson]

    def __init__(self):
        self.lessons = []

    def get_subjects(self, day: date, group: str | None = None, subgroup: str | None = None):
        filtered = [
            lesson_for_day
            for lesson in self.lessons
            if (lesson_for_day := lesson.for_day(day, group, subgroup)) is not None
        ]
        filtered.sort(key = lambda lesson: lesson.index)
        return filtered

    def make_from(self, data: dict[int, list[scheduler_parser.Lesson]], subject: Subject):
        for index, lessons in data.items():
            for lesson in lessons:
                self.lessons.append(Lesson.make_from(lesson, index, subject))


class GroupSchedule:
    days: dict[int, LessonList]# week_day -> LessonList
    start_year = scheduler_parser.academic_year_start()
    september_first = date(start_year, 9, 1)
    day_parser: DayParser = DayParser(
        september_first - timedelta(days=september_first.weekday())
    )

    def __init__(self):
        self.days = {}

    def parse_week(self, data: dict[int, dict[int, list[scheduler_parser.Lesson]]], even: bool, subject: Subject):
        for day, lessons in data.items():
            day_index = self.day_parser.make_index(day, even)
            if day_index not in self.days:
                self.days[day_index] = LessonList()
            self.days[day_index].make_from(lessons, subject)


    def parse(self, data: list[scheduler_parser.Subject]):
        for s in data:
            subject = Subject.make_from(s)
            self.parse_week(s.chet, True, subject)
            self.parse_week(s.nchet, False, subject)

    def get_day(
        self,
        day: date,
        group: str | None = None,
        subgroup: str | None = None,
    ) -> list[Lesson]:
        day_index = self.day_parser.parse(day)
        if day_index is not None:
            subject_list = self.days.get(day_index)
            if subject_list is None:
                return []
            return subject_list.get_subjects(day, group, subgroup)
        
        return []

class Scheduler:
    groups: dict[str, GroupSchedule]
    
    def __init__(self):
        self.groups = {}

    def parse_group(self, data: scheduler_parser.GroupSchedule):
        new_group = GroupSchedule()
        new_group.parse(data.subjects)
        self.groups[data.meta.group] = new_group

    def get_day(
        self,
        day: date,
        schedule_group: str,
        selected_group: str | None = None,
        subgroup: str | None = None,
    ):
        return self.groups[schedule_group].get_day(day, selected_group, subgroup)

    def get_subgroups(self, schedule_group: str, selected_group: str) -> list[str]:
        group_schedule = self.groups.get(schedule_group)
        if group_schedule is None:
            return []

        subgroups = {
            lesson.subgroup
            for lesson_list in group_schedule.days.values()
            for lesson in lesson_list.lessons
            if lesson.subgroup is not None and lesson.matches_group(selected_group)
        }
        return sorted(subgroups)


# from datetime import datetime, timedelta

# today = datetime.now().date()
    
# if __name__ == "__main__":
#     scheduler = Scheduler()
#     with open("scheduler/test.json", encoding="utf-8") as file:
#         parsed = scheduler_parser.parse_json(file.read())
#         scheduler.parse_group(parsed)
#     print(today +  + timedelta(days=1))
    
#     result = scheduler.get_day(today, "8101,02")
    
#     lesson_index = 0
#     for item in result:
#         if lesson_index != item.index:
#             lesson_index = item.index
#             print(f"{lesson_index} пара")
#         print(f"  {item.subject.name} ({item.cabinet}) - {'Лекция' if item.is_lecture() else item.type}")
