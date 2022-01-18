import math
from datetime import datetime


class TimeFormat:
    TIME = "t"
    TIME_LONG = "T"
    DATE = "d"
    DATE_LONG = "D"
    FULL = "f"
    FULL_LONG = "F"
    RELATIVE = "R"


def time(t: datetime, time_format=TimeFormat.TIME):
    utc = math.floor(t.timestamp())
    return f"<t:{utc}:{time_format}>"


def role(r):
    return f"<@&{r}>"


def user(u):
    return f"<@{u}>"


def channel(c):
    return f"<#{c}>"
