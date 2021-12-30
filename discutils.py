import math
from datetime import datetime


def timestamp(time: datetime):
    utc = math.floor(time.timestamp())
    return f"<t:{utc}:t>"


def user_dict(user) -> dict:
    return {"id": user.id, "name": user.display_name, "mention": user.mention}
