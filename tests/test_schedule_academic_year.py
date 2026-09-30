import unittest
import json
from datetime import date
from pathlib import Path

from scheduler.schedule import DayParser, Scheduler
from scheduler.scheduler_parser import Period, parse_json
from bot.handlers import format_lesson


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AcademicYearTests(unittest.TestCase):
    def test_multiple_lessons_can_share_the_same_pair(self):
        source = {
            "meta": {"group": "test"},
            "subjects": [
                {
                    "name": "Тестовый предмет",
                    "period": {"practice": {"from": "01.09", "to": "30.09"}},
                    "nchet": {
                        "tuesday": {
                            "par_2": [
                                {"type": "21", "classroom": [{"room": "ВСТ-210"}]},
                                {"type": "21Н", "classroom": [{"room": "Д-404"}]},
                            ]
                        }
                    },
                    "teachers": [{"name": "Преподаватель"}],
                }
            ],
        }

        parsed = parse_json(json.dumps(source, ensure_ascii=False))
        scheduler = Scheduler()
        scheduler.parse_group(parsed)
        lessons = scheduler.groups["test"].days[1].lessons

        self.assertEqual(len(lessons), 2)
        self.assertEqual([lesson.index for lesson in lessons], [2, 2])
        self.assertEqual([lesson.type for lesson in lessons], ["21", "21Н"])
        self.assertEqual([lesson.cabinet for lesson in lessons], ["ВСТ-210", "Д-404"])

    def test_lesson_with_specific_date_is_not_repeated(self):
        source = {
            "meta": {"group": "dated"},
            "subjects": [
                {
                    "name": "Разовое занятие",
                    "period": {"lecture": {"from": "01.09", "to": "30.09"}},
                    "nchet": {
                        "wednesday": {
                            "par_1": {
                                "type": "Л",
                                "classroom": [{"room": "З-102", "date": "02.09"}],
                            }
                        }
                    },
                    "teachers": [{"name": "Преподаватель"}],
                }
            ],
        }

        parsed = parse_json(json.dumps(source, ensure_ascii=False))
        scheduler = Scheduler()
        scheduler.parse_group(parsed)

        self.assertEqual(len(scheduler.get_day(date(2026, 9, 2), "dated")), 1)
        self.assertEqual(scheduler.get_day(date(2026, 9, 16), "dated"), [])

    def test_classroom_date_limits_are_applied(self):
        source = {
            "meta": {"group": "limited"},
            "subjects": [
                {
                    "name": "Занятие с заменой аудитории",
                    "period": {"practice": {"from": "01.09", "to": "30.11"}},
                    "nchet": {
                        "wednesday": {
                            "par_2": {
                                "type": "21",
                                "classroom": [
                                    {"room": "Д-404", "until": "30.09"},
                                    {"room": "ВСТ-210", "from": "01.10"},
                                ],
                            }
                        }
                    },
                    "teachers": [{"name": "Преподаватель"}],
                }
            ],
        }

        parsed = parse_json(json.dumps(source, ensure_ascii=False))
        scheduler = Scheduler()
        scheduler.parse_group(parsed)

        september = scheduler.get_day(date(2026, 9, 16), "limited")
        october = scheduler.get_day(date(2026, 10, 14), "limited")
        self.assertEqual([lesson.cabinet for lesson in september], ["Д-404"])
        self.assertEqual([lesson.cabinet for lesson in october], ["ВСТ-210"])

    def test_lessons_are_filtered_by_group_and_subgroup(self):
        source = {
            "meta": {"group": "8101,02,03"},
            "subjects": [
                {
                    "name": "Тестовый предмет",
                    "period": {"lecture": {"from": "01.09", "to": "30.09"}},
                    "nchet": {
                        "wednesday": {
                            "par_1": [
                                {
                                    "type": "1А",
                                    "group": "8101",
                                    "subgroup": "А",
                                    "classroom": [{"room": "Д-236"}],
                                },
                                {
                                    "type": "1Б",
                                    "group": "8101",
                                    "subgroup": "Б",
                                    "classroom": [{"room": "Д-233"}],
                                },
                                {
                                    "type": "Л",
                                    "groups": ["8101", "8102", "8103"],
                                    "classroom": [{"room": "НК-549"}],
                                },
                            ]
                        }
                    },
                    "teachers": [{"name": "Преподаватель"}],
                }
            ],
        }

        parsed = parse_json(json.dumps(source, ensure_ascii=False))
        scheduler = Scheduler()
        scheduler.parse_group(parsed)

        group_8101_a = scheduler.get_day(
            date(2026, 9, 2), "8101,02,03", "8101", "А"
        )
        group_8101_b = scheduler.get_day(
            date(2026, 9, 2), "8101,02,03", "8101", "Б"
        )
        group_8102 = scheduler.get_day(
            date(2026, 9, 2), "8101,02,03", "8102", "А"
        )

        self.assertEqual([lesson.type for lesson in group_8101_a], ["1А", "Л"])
        self.assertEqual([lesson.type for lesson in group_8101_b], ["1Б", "Л"])
        self.assertEqual([lesson.type for lesson in group_8102], ["Л"])
        self.assertEqual(
            scheduler.get_subgroups("8101,02,03", "8101"),
            ["А", "Б"],
        )

    def test_week_containing_september_first_is_odd(self):
        parser = DayParser(date(2026, 8, 31))

        self.assertEqual(parser.parse(date(2026, 9, 1)), 1)
        self.assertEqual(parser.parse(date(2026, 9, 6)), 6)

    def test_week_after_first_academic_week_is_even(self):
        parser = DayParser(date(2026, 8, 31))

        self.assertEqual(parser.parse(date(2026, 9, 7)), 7)
        self.assertEqual(parser.parse(date(2026, 9, 13)), 13)

    def test_academic_week_parity_continues_alternating(self):
        parser = DayParser(date(2026, 8, 31))

        self.assertEqual(parser.parse(date(2026, 9, 14)), 0)

    def test_period_crossing_new_year_is_valid(self):
        period = Period.model_validate({"from": "19.10", "to": "16.01"})
        self.assertLess(period.start, period.end)
        self.assertEqual(period.end.year, period.start.year + 1)

    def test_schedule_without_teacher_can_be_loaded(self):
        source = PROJECT_ROOT / "scheduler" / "jsons" / "1122а.json"
        parsed = parse_json(source.read_text(encoding="utf-8"))
        self.assertTrue(any(not subject.teachers for subject in parsed.subjects))

        scheduler = Scheduler()
        scheduler.parse_group(parsed)
        self.assertIn(parsed.meta.group, scheduler.groups)

    def test_all_current_schedule_json_files_load(self):
        json_dir = PROJECT_ROOT / "scheduler" / "jsons"
        scheduler = Scheduler()

        for source in json_dir.glob("*.json"):
            with self.subTest(source=source.name):
                scheduler.parse_group(parse_json(source.read_text(encoding="utf-8")))

    def test_lesson_output_contains_teacher(self):
        source = PROJECT_ROOT / "scheduler" / "jsons" / "1122а.json"
        scheduler = Scheduler()
        parsed = parse_json(source.read_text(encoding="utf-8"))
        scheduler.parse_group(parsed)

        lesson = next(
            lesson
            for day in scheduler.groups[parsed.meta.group].days.values()
            for lesson in day.lessons
            if lesson.subject.teacher
        )
        text = format_lesson(lesson)

        self.assertIn("Преподаватель:", text)
        self.assertIn(lesson.subject.teacher, text)


if __name__ == "__main__":
    unittest.main()
