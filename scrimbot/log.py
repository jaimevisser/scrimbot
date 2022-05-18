import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Callable


class Log:

    def __init__(self, data: list, sync: Callable):
        self.__log = data
        self.__sync = sync

    def add_note(self, user: int, author: int, text: str):
        self.__add_entry("note", user, author, text)

    def add_warning(self, user: int, author: int, text: str):
        self.__add_entry("warning", user, author, text)

    def add_report(self, channel: int, user: int, author: int, text: str):
        self.__add_entry("report", user, author, text, channel=channel)

    def add_kick(self, channel: int, user: int, author: int, text: str):
        self.__add_entry("scrim-kick", user, author, text, channel=channel)

    def add_timeout(self, user: int, author: int, text: str):
        self.__add_entry("timeout", user, author, text)

    def add_scrim(self, user: int, text: str):
        self.__add_entry("scrim", user, 0, text)

    def __add_entry(self, type: str, user: int, author: int, text: str, **kwargs):
        entry = {
            "id": uuid.uuid4().hex[0:16],
            "user": user,
            "time": datetime.now(timezone.utc).timestamp(),
            "text": text,
            "author": author,
            "type": type}
        entry.update(kwargs)

        self.__log.append(entry)
        self.__sync()

    def warning_count(self, user: int) -> int:
        return len([d for d in self.__log if d['type'] == "warning" and d['user'] == user])

    def daily_report_count(self, user: int) -> int:
        start_time = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()

        return len([d for d in self.__log
                    if d['type'] == "report" and d['author'] == user and d['time'] > start_time])

    def remove(self, predicate) -> int:

        to_remove = [x for x in self.__log if predicate(x)]

        if len(to_remove) > 0:
            for logentry in to_remove:
                self.__log.remove(logentry)
            self.__sync()
        return len(to_remove)

    ALL = ["warning", "note", "report", "scrim-kick", "timeout", "scrim"]

    def print_log(self, user: int, types=None, authors=False) -> list:
        if types is None:
            types = ["warning"]

        entries = [x for x in self.__log if x["type"] in types and (x["user"] == user or x["author"] == user)]
        output = []

        for entry in entries:
            start = f"[{entry['id']}] <t:{math.floor(entry['time'])}:d>"
            author = f" by <@{entry['author']}>" if authors else ""
            if entry["type"] == "note" and entry["user"] == user:
                output.append(f"{start} note{author}: {entry['text']}")
            elif entry["type"] == "warning" and entry["user"] == user:
                output.append(f"{start} ⚠ got warned{author}: {entry['text']}")
            elif entry["type"] == "warning" and entry["author"] == user:
                output.append(f"{start} warned <@{entry['user']}>: {entry['text']}")
            elif entry["type"] == "report" and entry["user"] == user:
                output.append(f"{start} ⚠ got reported{author} in <#{entry['channel']}>: {entry['text']}")
            elif entry["type"] == "report" and entry["author"] == user:
                output.append(f"{start} reported <@{entry['user']}> in <#{entry['channel']}>: {entry['text']}")
            elif entry["type"] == "scrim-kick" and entry["user"] == user:
                output.append(f"{start} ⚠ got kicked from a scrim{author} in <#{entry['channel']}>: {entry['text']}")
            elif entry["type"] == "scrim-kick" and entry["author"] == user:
                output.append(
                    f"{start} kicked <@{entry['user']}> from a scrim in <#{entry['channel']}>: {entry['text']}")
            elif entry["type"] == "timeout" and entry["user"] == user:
                output.append(f"{start} ⚠ was put on a timeout{author}: {entry['text']}")
            elif entry["type"] == "timeout" and entry["author"] == user:
                output.append(f"{start} timed out <@{entry['user']}>: {entry['text']}")
            elif entry["type"] == "scrim" and entry["user"] == user:
                output.append(f"{start} (probably) played a scrim: {entry['text']}")

        return output
