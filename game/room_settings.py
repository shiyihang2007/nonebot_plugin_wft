from pydantic import BaseModel


class RoomSettings(BaseModel):
    debug: bool = False
