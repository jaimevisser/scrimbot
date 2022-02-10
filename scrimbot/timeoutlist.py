from collections import namedtuple
import discord
import asyncio
from datetime import datetime, timedelta, timezone


class TimeoutList(list):
    """List to keep track of the users in timeout. Users are represented as `NamedTuple` with id, timeout and runout_task."""
    User = namedtuple("User", 
                      ["id", "timeout", "runout_task"], 
                      defaults=[None])
    Snowflake = namedtuple("Snowflake", "id")

    def __init__(self, guild, users):
        self.guild = guild
        self.bot = guild.bot
        l = []
        for u in users:
            task = self.bot.loop.create_task(self._timeout_runout(u["user_id"]))
            l.append(self.User(u["user_id"],
                               datetime.fromisoformat(u["timeout"]),
                               task))
        super().__init__(l)
        
    async def _timeout_runout(self, user_id):
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
        self.guild._Guild__sync(self._to_list(), "timeouts")    # I dislike name mangling

    def _to_list(self):
        l = []
        for u in self:
            d = {"user_id": u.id,
                 "timeout": u.timeout.isoformat()}
            l.append(d)
        return l
    
    def _get_user_from_id(self, user_id):
        user = next((u for u in self if u.id == user_id), None)
        return user

    def add_user(self, user_id, duration):
        loop = self.bot.loop
        loop.create_task(self._add_role(user_id))
        loop.create_task(self._remove_user_from_scrims(user_id))
        task = loop.create_task(self._timeout_runout(user_id))

        u = self.User(user_id, datetime.now(tz=timezone.utc)+duration, task)
        self.append(u)
        self._sync()

    def remove_user(self, user_id):
        self.bot.loop.create_task(self._remove_role(user_id))
        user = self._get_user_from_id(user_id)
        user_index = self.index(user)
        del self[user_index]
        self._sync()
        user.runout_task.cancel()

    def is_timeout(self, user_id):
        """
        Returns: 
            bool: if user is in timeout"""
        user = self._get_user_from_id(user_id)
        if user is None:
            return False
        return True
    
    def user_timeout(self, user_id):
        "Get remaining timeout for a user truncated after seconds or None."
        user = self._get_user_from_id(user_id)
        if user is None:
            return None
        timeout = user.timeout - datetime.now(tz=timezone.utc)
        return timedelta(timeout.days, timeout.seconds)
    
    async def _add_role(self, user_id, reason=None):
        if not self.guild.timeout_role:
            return
        dc_guild = self.bot.get_guild(int(self.guild.id))
        member = await dc_guild.fetch_member(user_id)
        if member:
            role = self.Snowflake(self.guild.timeout_role)
            await member.add_roles(role, reason=reason)
    
    async def _remove_role(self, user_id, reason=None):
        if not self.guild.timeout_role:
            return
        dc_guild = self.bot.get_guild(int(self.guild.id))
        member = await dc_guild.fetch_member(user_id)
        if member:
            role = self.Snowflake(self.guild.timeout_role)
            await member.remove_roles(role, reason=reason)
