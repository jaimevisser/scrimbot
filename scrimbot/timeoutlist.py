import asyncio
from collections import namedtuple
from datetime import datetime, timedelta, timezone


class TimeoutList:
    """List to keep track of the users in timeout. Users are represented 
    as `NamedTuple` with id, timeout and runout_task."""
    User = namedtuple("User",
                      ["id", "timeout", "runout_task"],
                      defaults=[None])

    def __init__(self, guild, store):
        self.guild = guild
        self.loop = guild.bot.loop
        self._store = store
        users = store.data
        self._timeouts = []
        for u in users:
            task = self.loop.create_task(self._timeout_countdown(u["user_id"]))
            self._timeouts.append(
                self.User(u["user_id"],
                          datetime.fromtimestamp(u["timeout"], timezone.utc),
                          task)
            )

    def contains_user(self, user_id):
        return any(u.id == user_id for u in self._timeouts)

    async def _timeout_countdown(self, user_id):
        user = self._get_user_from_id(user_id)
        timeout_left = user.timeout - datetime.now(tz=timezone.utc)
        await asyncio.sleep(timeout_left.total_seconds())
        self.remove_user(user.id)

    async def _remove_user_from_scrims(self, user_id):
        user = self._get_user_from_id(user_id)
        for scrim_mgr in self.guild.scrim_managers:
            if scrim_mgr.scrim.time > user.timeout:
                continue
            await scrim_mgr.leave(user)

    def _sync(self):
        self._store.data = self._to_list()
        self.guild.queue_callable(self._store.sync)()

    def _to_list(self):
        l = []
        for u in self._timeouts:
            d = {"user_id": u.id,
                 "timeout": u.timeout.timestamp()}
            l.append(d)
        return l

    def _get_user_from_id(self, user_id):
        user = next((u for u in self._timeouts if u.id == user_id), None)
        return user

    def add_user(self, user_id, duration, reason):
        self.loop.create_task(self._add_role(user_id, reason))
        self.loop.create_task(self._remove_user_from_scrims(user_id))
        task = self.loop.create_task(self._timeout_countdown(user_id))

        u = self.User(user_id, datetime.now(tz=timezone.utc) + duration, task)
        self._timeouts.append(u)
        self._sync()

    def remove_user(self, user_id, reason=None):
        self.loop.create_task(self._remove_role(user_id, reason))
        user = self._get_user_from_id(user_id)
        user_index = self._timeouts.index(user)
        del self._timeouts[user_index]
        self._sync()
        user.runout_task.cancel()

    def time_remaining(self, user_id):
        "Get remaining timeout for a user truncated after seconds or None."
        user = self._get_user_from_id(user_id)
        if user is None:
            return None
        timeout = user.timeout - datetime.now(tz=timezone.utc)
        return timedelta(timeout.days, timeout.seconds)

    async def _add_role(self, user_id, reason=None):
        await self.guild.add_timeout_role(user_id, reason)

    async def _remove_role(self, user_id, reason=None):
        await self.guild.remove_timeout_role(user_id, reason=reason)
