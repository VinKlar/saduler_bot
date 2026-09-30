import time


STATE_TIMEOUT_SECONDS = 120


class Event:
    def __init__(self, update: dict):
        self.update = update
        self.update_type = update.get("update_type")

        self.message = update.get("message", {})
        self.callback = update.get("callback", {})

        self.type = "unknown"
        self.user_id = None
        self.chat_id = None
        self.text = None
        self.payload = None

        if self.update_type == "message_created":
            self.type = "message"
            self.user_id = self.message["sender"]["user_id"]
            self.chat_id = self.message["recipient"]["chat_id"]
            self.text = (
                self.message
                .get("body", {})
                .get("text", "")
                .strip()
            )

        elif self.update_type == "message_callback":
            self.type = "callback"
            self.user_id = self.callback["user"]["user_id"]
            self.chat_id = self.message["recipient"]["chat_id"]
            self.payload = self.callback.get("payload")

        elif self.update_type == "bot_started":
            self.type = "bot_started"
            user = self.update.get("user", {})
            self.user_id = user.get("user_id", self.update.get("user_id"))
            self.chat_id = self.update.get("chat_id")
            self.payload = self.update.get("payload")


class Router:
    def __init__(self):
        self.message_handlers = []
        self.callback_handlers = []
        self.command_handlers = []
        self.state_handlers = []
        self.start_handlers = []
        self.missing_user_handlers = []
        self.state_timeout_handlers = []

    def message(self, text=None):
        def decorator(func):
            self.message_handlers.append({
                "text": text,
                "func": func
            })
            return func

        return decorator

    def callback(self, payload=None):
        def decorator(func):
            self.callback_handlers.append({
                "payload": payload,
                "func": func
            })
            return func

        return decorator

    def command(self, command_name):
        def decorator(func):
            self.command_handlers.append({
                "command": command_name,
                "func": func
            })
            return func

        return decorator

    def state(self, state_name):
        def decorator(func):
            self.state_handlers.append({
                "state": state_name,
                "func": func
            })
            return func

        return decorator

    def bot_started(self):
        def decorator(func):
            self.start_handlers.append(func)
            return func

        return decorator

    def missing_user(self):
        def decorator(func):
            self.missing_user_handlers.append(func)
            return func

        return decorator

    def state_timeout(self):
        def decorator(func):
            self.state_timeout_handlers.append(func)
            return func

        return decorator

    @staticmethod
    async def _run_handler(func, event, context):
        await func(event, context)

        state_updated = context.setdefault("USER_STATE_UPDATED", {})
        if context["USER_STATE"].get(event.user_id):
            state_updated[event.user_id] = time.monotonic()
        else:
            state_updated.pop(event.user_id, None)

    async def dispatch(self, update: dict, context: dict):
        event = Event(update)

        if event.type == "unknown":
            return

        user_state = context["USER_STATE"].get(event.user_id)
        state_updated = context.setdefault("USER_STATE_UPDATED", {})

        if event.type == "message" and event.text == "/restart":
            for handler in self.command_handlers:
                if handler["command"] == "restart":
                    await self._run_handler(handler["func"], event, context)
                    return

        if user_state:
            updated_at = state_updated.setdefault(event.user_id, time.monotonic())
            if time.monotonic() - updated_at >= STATE_TIMEOUT_SECONDS:
                context["USER_STATE"].pop(event.user_id, None)
                context["USER_SELECTION"].pop(event.user_id, None)
                state_updated.pop(event.user_id, None)

                for handler in self.state_timeout_handlers:
                    await self._run_handler(handler, event, context)
                return

        is_start_message = event.type == "message" and event.text == "/start"
        user_exists = context["USERS"].get(str(event.user_id)) is not None

        if (
            not user_exists
            and not user_state
            and event.type != "bot_started"
            and not is_start_message
        ):
            for handler in self.missing_user_handlers:
                await self._run_handler(handler, event, context)
            return

        if event.type == "callback" and event.payload == "cancel":
            for handler in self.callback_handlers:
                if handler["payload"] == "cancel":
                    await self._run_handler(handler["func"], event, context)
                    return

        if user_state:
            for handler in self.state_handlers:
                if handler["state"] == user_state:
                    await self._run_handler(handler["func"], event, context)
                    return

        if event.type == "bot_started":
            for handler in self.start_handlers:
                await self._run_handler(handler, event, context)
            return

        if event.type == "message" and event.text.startswith("/"):
            command = event.text.split()[0][1:]

            for handler in self.command_handlers:
                if handler["command"] == command:
                    await self._run_handler(handler["func"], event, context)
                    return

        if event.type == "message":
            for handler in self.message_handlers:
                if handler["text"] is None or handler["text"] == event.text:
                    await self._run_handler(handler["func"], event, context)
                    return

        if event.type == "callback":
            for handler in self.callback_handlers:
                if handler["payload"] is None or handler["payload"] == event.payload:
                    await self._run_handler(handler["func"], event, context)
                    return
