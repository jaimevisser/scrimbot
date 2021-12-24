import math
from datetime import datetime


def timestamp(time: datetime):
    utc = math.floor(time.timestamp())
    return f"<t:{utc}:t>"
