import math
from datetime import datetime

import discord


def timestamp(time: datetime):
    utc = math.floor(time.timestamp())
    return f"<t:{utc}:t>"


def user_dict(user: discord.Member) -> dict:
    return {"id": user.id, "name": user.display_name, "mention": user.mention}


