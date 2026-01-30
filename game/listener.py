from typing import Any


class Listener:
    async def __call__(self, room: Any, user_id: str | None, args: list[str]) -> Any:
        pass
