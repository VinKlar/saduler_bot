import unittest
from unittest.mock import AsyncMock, patch

from bot.group_catalog import GROUP_CATALOG
from bot.handlers import router


def message_update(text, user_id=1, chat_id=10):
    return {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": user_id},
            "recipient": {"chat_id": chat_id},
            "body": {"text": text},
        },
    }


def callback_update(payload, user_id=1, chat_id=10):
    return {
        "update_type": "message_callback",
        "callback": {"user": {"user_id": user_id}, "payload": payload},
        "message": {"recipient": {"chat_id": chat_id}},
    }


def bot_started_update(user_id=1, chat_id=10, payload=None):
    return {
        "update_type": "bot_started",
        "timestamp": 0,
        "chat_id": chat_id,
        "user": {
            "user_id": user_id,
            "name": "Новый пользователь",
        },
        "payload": payload,
    }


class GroupCatalogTests(unittest.TestCase):
    def test_direct_group_search_ignores_spaces_case_and_final_dot(self):
        group = GROUP_CATALOG.find_group(" 1122 Э. ")
        self.assertIsNotNone(group)
        self.assertEqual(group["direction_code"], "35.04.03")

    def test_direction_can_be_found_by_code_and_name(self):
        matches = GROUP_CATALOG.search_directions("09.03.03 Прикладная информатика")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["code"], "09.03.03")


class RegistrationFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.saved_users = None
        self.context = {
            "USERS": {},
            "USER_STATE": {},
            "USER_SELECTION": {},
            "save_users": self.save_users,
        }

    def save_users(self, users):
        self.saved_users = dict(users)

    async def test_system_start_button_opens_registration(self):
        sender = AsyncMock()

        with patch("bot.handlers.send_message", new=sender):
            await router.dispatch(bot_started_update(), self.context)

        self.assertEqual(self.context["USER_STATE"][1], "WAIT_SEARCH")
        sender.assert_awaited_once()
        self.assertEqual(sender.await_args.args[1], "selection")
        self.assertIn(
            "Добро пожаловать в бот расписания",
            sender.await_args.kwargs["text"],
        )

    async def test_missing_user_is_sent_to_group_selection(self):
        sender = AsyncMock()

        with patch("bot.handlers.send_message", new=sender):
            await router.dispatch(callback_update("today"), self.context)

        self.assertEqual(self.context["USER_STATE"][1], "WAIT_SEARCH")
        sender.assert_awaited_once()
        self.assertEqual(sender.await_args.args[1], "selection")
        self.assertIn(
            "Не удалось найти сохранённую группу",
            sender.await_args.kwargs["text"],
        )

    async def test_group_deep_link_selects_group(self):
        sender = AsyncMock()

        with patch("bot.handlers.send_message", new=sender):
            await router.dispatch(
                bot_started_update(payload="group_8101"),
                self.context,
            )

        self.assertEqual(self.context["USERS"]["1"]["group"], "8101")
        self.assertNotIn(1, self.context["USER_STATE"])
        self.assertIsNotNone(self.saved_users)
        self.assertIn("Группа сохранена: 8101", sender.await_args.kwargs["text"])

    async def test_unknown_group_deep_link_opens_manual_selection(self):
        sender = AsyncMock()

        with patch("bot.handlers.send_message", new=sender):
            await router.dispatch(
                bot_started_update(payload="group_9999"),
                self.context,
            )

        self.assertEqual(self.context["USER_STATE"][1], "WAIT_SEARCH")
        self.assertIn("Группа 9999 не найдена", sender.await_args.kwargs["text"])

    async def test_user_can_enter_group_immediately(self):
        with patch("bot.handlers.send_message", new=AsyncMock()):
            await router.dispatch(message_update("/start"), self.context)
            self.assertEqual(self.context["USER_STATE"][1], "WAIT_SEARCH")
            await router.dispatch(message_update("8101"), self.context)

        self.assertEqual(self.context["USERS"]["1"]["group"], "8101")
        self.assertNotIn(1, self.context["USER_STATE"])
        self.assertIsNotNone(self.saved_users)

    async def test_direction_profile_group_flow(self):
        sender = AsyncMock()
        with patch("bot.handlers.send_message", new=sender):
            await router.dispatch(message_update("/start"), self.context)
            await router.dispatch(
                message_update("09.03.03 Прикладная информатика"),
                self.context,
            )

            selection = self.context["USER_SELECTION"][1]
            direction = GROUP_CATALOG.get_direction(selection["direction_id"])
            profile = direction["profiles"][0]
            await router.dispatch(
                callback_update(f"profile:{direction['id']}:{profile['id']}"),
                self.context,
            )
            self.assertEqual(self.context["USER_STATE"][1], "WAIT_GROUP")

            group = profile["groups"][0]
            await router.dispatch(callback_update(f"group:{group}"), self.context)

        self.assertEqual(self.context["USERS"]["1"]["group"], group)
        self.assertGreaterEqual(sender.await_count, 4)

    async def test_user_selects_subgroup_after_group(self):
        class ScheduleStub:
            @staticmethod
            def get_subgroups(schedule_group, selected_group):
                return ["А", "Б"] if selected_group == "8101" else []

        self.context["FGS"] = {"8101": "8101,02,03"}
        self.context["sched"] = ScheduleStub()

        with patch("bot.handlers.send_message", new=AsyncMock()):
            await router.dispatch(message_update("/start"), self.context)
            await router.dispatch(message_update("8101"), self.context)

            self.assertEqual(self.context["USER_STATE"][1], "WAIT_SUBGROUP")
            self.assertNotIn("1", self.context["USERS"])

            await router.dispatch(callback_update("subgroup:А"), self.context)

        self.assertEqual(
            self.context["USERS"]["1"],
            {"group": "8101", "subgroup": "А"},
        )

    async def test_settings_menu_contains_change_actions(self):
        self.context["USERS"]["1"] = {"group": "8101", "subgroup": "А"}
        sender = AsyncMock()

        with patch("bot.handlers.send_message", new=sender):
            await router.dispatch(callback_update("settings"), self.context)

        buttons = sender.await_args.kwargs["buttons"]
        payloads = [button["payload"] for row in buttons for button in row]
        self.assertEqual(
            payloads,
            ["settings_subgroup", "settings_group", "settings_direction"],
        )


if __name__ == "__main__":
    unittest.main()
