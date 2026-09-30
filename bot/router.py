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
            self.user_id = self.update["user_id"]
            self.chat_id = self.update["chat_id"]


class Router:
    def __init__(self):
        self.message_handlers = []
        self.callback_handlers = []
        self.command_handlers = []
        self.state_handlers = []
        self.start_handlers = []

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

    async def dispatch(self, update: dict, context: dict):
        event = Event(update)

        if event.type == "unknown":
            return

        user_state = context["USER_STATE"].get(event.user_id)

        if event.type == "callback" and event.payload == "cancel":
            for handler in self.callback_handlers:
                if handler["payload"] == "cancel":
                    await handler["func"](event, context)
                    return

        if user_state:
            for handler in self.state_handlers:
                if handler["state"] == user_state:
                    await handler["func"](event, context)
                    return

        if event.type == "bot_started":
            for handler in self.start_handlers:
                await handler(event, context)
            return

        if event.type == "message" and event.text.startswith("/"):
            command = event.text.split()[0][1:]

            for handler in self.command_handlers:
                if handler["command"] == command:
                    await handler["func"](event, context)
                    return

        if event.type == "message":
            for handler in self.message_handlers:
                if handler["text"] is None or handler["text"] == event.text:
                    await handler["func"](event, context)
                    return

        if event.type == "callback":
            for handler in self.callback_handlers:
                if handler["payload"] is None or handler["payload"] == event.payload:
                    await handler["func"](event, context)
                    return