import math
from datetime import datetime

from discord import Member


def timestamp(time: datetime):
    utc = math.floor(time.timestamp())
    return f"<t:{utc}:t>"


def user_dict(user) -> dict:
    return {"id": user.id, "name": user.display_name, "mention": user.mention}


def has_role(user: Member, role: int) -> bool:
    for r in user.roles:
        if r.id == role:
            return True
    return False
