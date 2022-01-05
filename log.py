import math
import uuid
from datetime import datetime, timezone
from typing import Callable


class Log:
    ALL = ["warning", "note"]

    def __init__(self, get_log: Callable, sync: Callable):
        self.__get_log = get_log
        self.__sync = sync

    def add_note(self, guild: str, user: int, author: int, text: str):
        self.__add_entry("note", guild, user, author, text)

    def add_warning(self, guild: str, user: int, author: int, text: str):
        self.__add_entry("warning", guild, user, author, text)

    def __add_entry(self, type: str, guild: str, user: int, author: int, text: str):
        self.__get_log(guild).append({
            "id": uuid.uuid4().hex[0:16],
            "user": user,
            "time": datetime.now(timezone.utc).timestamp(),
            "text": text,
            "author": author,
            "type": type})
        self.__sync()

    def warning_count(self, guild: str, user: int) -> int:
        return len([d for d in self.__get_log(guild) if d['type'] == "warning" and d['user'] == user])

    def remove(self, guild: str, predicate) -> int:

        all_guild_entries = self.__get_log(guild)

        to_remove = [x for x in all_guild_entries if predicate(x)]

        if len(to_remove) > 0:
            for logentry in to_remove:
                all_guild_entries.remove(logentry)
            self.__sync()
        return len(to_remove)

    def print_log(self, guild: str, user: int, types=None) -> list:
        all_guild_entries = self.__get_log(guild)

        if types is None:
            types = ["warning"]

        entries = [x for x in all_guild_entries if x["type"] in types and (x["user"] == user or x["author"] == user)]
        print = []

        for entry in entries:
            start = f"[{entry['id']}] <t:{math.floor(entry['time'])}:d>"
            if entry["type"] == "note" and entry["user"] == user:
                print.append(f"{start} note by <@{entry['author']}>: {entry['text']}")
            elif entry["type"] == "warning" and entry["user"] == user:
                print.append(f"{start} ⚠ got warned by <@{entry['author']}>: {entry['text']}")
            elif entry["type"] == "warning" and entry["author"] == user:
                print.append(f"{start} warned <@{entry['user']}>: {entry['text']}")

        return print
