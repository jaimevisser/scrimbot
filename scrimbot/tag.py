import math
from datetime import datetime


class Format:
    TIME = "t"
    RELATIVE = "R"


def time(t: datetime, format="t"):
    utc = math.floor(t.timestamp())
    return f"<t:{utc}:{format}>"
