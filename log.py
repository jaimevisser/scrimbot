import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Callable


class Log:

    def __init__(self, get_log: Callable, sync: Callable):
        self.__get_log = get_log
        self.__sync = sync

    def add_note(self, guild: str, user: int, author: int, text: str):
        self.__add_entry("note", guild, user, author, text)

    def add_warning(self, guild: str, user: int, author: int, text: str):
        self.__add_entry("warning", guild, user, author, text)

    def add_report(self, guild: str, channel: int, user: int, author: int, text: str):
        self.__add_entry("report", guild, user, author, text, channel=channel)

    def __add_entry(self, type: str, guild: str, user: int, author: int, text: str, **kwargs):
        entry = {
            "id": uuid.uuid4().hex[0:16],
            "user": user,
            "time": datetime.now(timezone.utc).timestamp(),
            "text": text,
            "author": author,
            "type": type}
        entry.update(kwargs)

        self.__get_log(guild).append(entry)
        self.__sync()

    def warning_count(self, guild: str, user: int) -> int:
        return len([d for d in self.__get_log(guild) if d['type'] == "warning" and d['user'] == user])

    def daily_report_count(self, guild: str, user: int) -> int:
        start_time = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()

        return len([d for d in self.__get_log(guild)
                    if d['type'] == "report" and d['author'] == user and d['time'] > start_time])

    def remove(self, guild: str, predicate) -> int:

        all_guild_entries = self.__get_log(guild)

        to_remove = [x for x in all_guild_entries if predicate(x)]

        if len(to_remove) > 0:
            for logentry in to_remove:
                all_guild_entries.remove(logentry)
            self.__sync()
        return len(to_remove)

    ALL = ["warning", "note", "report"]

    def print_log(self, guild: str, user: int, types=None, authors=False) -> list:
        all_guild_entries = self.__get_log(guild)

        if types is None:
            types = ["warning"]

        entries = [x for x in all_guild_entries if x["type"] in types and (x["user"] == user or x["author"] == user)]
        print = []

        for entry in entries:
            start = f"[{entry['id']}] <t:{math.floor(entry['time'])}:d>"
            author = f" by <@{entry['author']}>" if authors else ""
            if entry["type"] == "note" and entry["user"] == user:
                print.append(f"{start} note{author}: {entry['text']}")
            elif entry["type"] == "warning" and entry["user"] == user:
                print.append(f"{start} ⚠ got warned{author}: {entry['text']}")
            elif entry["type"] == "warning" and entry["author"] == user:
                print.append(f"{start} warned <@{entry['user']}>: {entry['text']}")
            elif entry["type"] == "report" and entry["user"] == user:
                print.append(f"{start} ⚠ got reported{author} in <#{entry['channel']}>: {entry['text']}")
            elif entry["type"] == "report" and entry["author"] == user:
                print.append(f"{start} reported <@{entry['user']}> in <#{entry['channel']}>: {entry['text']}")

        return print
