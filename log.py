import uuid
from datetime import datetime, timezone
from typing import Callable


class Log:

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

    def remove(self, guild: str, predicate):
        to_remove = []

        all_guild_entries = self.__get_log(guild)

        for logentry in all_guild_entries:
            if predicate(logentry):
                to_remove.append(logentry)

        if len(to_remove) > 0:
            for logentry in to_remove:
                all_guild_entries.remove(logentry)
            self.__sync()
        return len(to_remove)