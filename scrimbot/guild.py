import asyncio
import logging
from collections import namedtuple
from datetime import timedelta
from typing import Optional, Callable, Coroutine, Any

import discord
import pytz

import scrimbot

_log = logging.getLogger(__name__)

Snowflake = namedtuple("Snowflake", "id")


class Guild:

    def __init__(self, id: str, config: dict, bot: discord.Bot):
        self.id = str(id)
        self.name = str(id)
        self.config = config
        self.bot: discord.Bot = bot
        __log_store = scrimbot.Store[list](f"data/{self.id}-log.json", [])
        self.__scrims = scrimbot.Store[list](f"data/{self.id}-scrims.json", [])
        _timeouts_store = scrimbot.Store[list](f"data/{self.id}-timeouts.json", [])
        self.log = scrimbot.Log(__log_store.data, self.queue_callable(__log_store.sync))
        self._timeouts = scrimbot.TimeoutList(self, _timeouts_store)
        self.mod_channel: Optional[discord.TextChannel] = None
        self.timezone = pytz.timezone(self.config["timezone"])
        self.scrim_managers: list[scrimbot.ScrimManager] = []
        self.broadcasts: list[scrimbot.Broadcaster] = []
        self.organiser_roles = None
        self.invite: Optional[discord.Invite] = None
        self.__invite_channel: Optional[discord.TextChannel] = None
        self.__guild: Optional[discord.Guild] = None
        self.__timeout_role = self.config.get("scrim", dict()).get("timeout_role", None)

        self.__defaults = self.config.get("scrim", dict()).copy()
        self.__defaults.pop("channels", None)

        for scrim in self.__scrims.data:
            self.__create_scrim(scrim)
        if "name" in self.config:
            self.name += " - " + self.config["name"]
        if "organiser_roles" in self.config:
            self.organiser_roles = set(self.config["organiser_roles"])

    @property
    def scrim_channels(self) -> dict[str, dict]:
        channels = self.config.get("scrim", dict()).get("channels", dict())
        for c in channels:
            if channels[c] is None:
                channels[c] = dict()
        return channels if channels is not None else dict()

    async def init(self):
        self.__guild = await self.bot.fetch_guild(int(self.id))
        self.mod_channel = await self.fetch_mod_channel()

        await self._timeouts.init()

        if "name" not in self.config:
            self.name += " - " + self.__guild.name

        scrims = self.scrim_managers.copy()
        for scrim in scrims:
            try:
                await scrim.init()
            except Exception as error:
                _log.error(f"Unable to properly initialise scrim {scrim.id} due to {error}")
                _log.exception(error)

        broadcast_channels = \
            set(s["broadcast_channel"] for s in self.scrim_channels.values() if "broadcast_channel" in s)

        for b in broadcast_channels:
            self.broadcasts.append(scrimbot.Broadcaster(b, self))

        for b in self.broadcasts:
            await b.update()

    async def fetch_mod_channel(self):
        if self.mod_channel is None:
            self.mod_channel = self.bot.get_channel(self.config["mod_channel"])
        if self.mod_channel is None:
            try:
                self.mod_channel = await self.bot.fetch_channel(self.config["mod_channel"])
            except discord.DiscordException as error:
                _log.error(f"{self.name}: Unable to properly load mod channel due to {error}")
        return self.mod_channel

    async def fetch_invite(self) -> discord.Invite:
        vanity = await self.__fetch_vanity_invite()
        if vanity is not None:
            return vanity
        if self.__invite_channel is None:
            await self.__fetch_invite_channel()
        if self.__invite_channel is not None:
            try:
                self.invite = await self.__invite_channel.create_invite(max_uses=0, max_age=0, unique=False)
                return self.invite
            except discord.DiscordException as error:
                _log.error(
                    f"{self.name}: Unable create an invite for channel {self.__invite_channel.id} due to {error}")

    async def __fetch_vanity_invite(self) -> discord.Invite:
        try:
            return await self.__guild.vanity_invite()
        except discord.DiscordException as error:
            _log.error(f"{self.name}: Unable to fetch vanity invite due to {error}")

    async def __fetch_invite_channel(self):
        if self.__invite_channel is None and "invite_channel" in self.config:
            self.__invite_channel = self.bot.get_channel(self.config["invite_channel"])
        if self.__invite_channel is None and "invite_channel" in self.config:
            try:
                self.__invite_channel = await self.bot.fetch_channel(self.config["invite_channel"])
            except discord.DiscordException as error:
                _log.error(f"{self.name}: Unable to properly load invite channel due to {error}")
        return self.__invite_channel

    def __create_scrim(self, data: dict) -> scrimbot.ScrimManager:
        scrim = self.create_scrim(data)
        return self.__create_scrim_manager(scrim)

    def create_scrim(self, data: dict) -> scrimbot.Scrim:
        scrim = scrimbot.Scrim(data=data, timezone=self.timezone, sync=self.queue_callable(self.__scrims.sync),
                               log=self.log)
        if scrim.scrim_channel is not None:
            scrim.settings = self.scrim_channel_config(scrim.scrim_channel)
        return scrim

    def __create_scrim_manager(self, scrim) -> scrimbot.ScrimManager:
        scrim_manager = scrimbot.ScrimManager(scrim=scrim,
                                              remove=self.__remove_scrim,
                                              update_broadcasts=self.__queue_coroutine(self.update_broadcasts),
                                              queue_task=self.queue_task,
                                              bot=self.bot,
                                              timeout_check=self.is_on_timeout)
        self.scrim_managers.append(scrim_manager)
        return scrim_manager

    def get_scrim_manager(self, id: int) -> scrimbot.ScrimManager:
        return next(filter(lambda s: s.id == id, self.scrim_managers), None)

    def __remove_scrim(self, scrim_manager):
        if scrim_manager in self.scrim_managers:
            self.scrim_managers.remove(scrim_manager)
        if scrim_manager.scrim.data in self.__scrims.data:
            self.__scrims.data.remove(scrim_manager.scrim.data)
        self.queue_callable(self.__scrims.sync)()

    def create_scrim_manager(self, scrim: scrimbot.Scrim):
        self.__scrims.data.append(scrim.data)
        self.queue_callable(self.__scrims.sync)()
        scrim_manager = self.__create_scrim_manager(scrim)
        self.queue_task(scrim_manager.init())

    def is_on_timeout(self, user: discord.Member) -> bool:
        if any(r.id == self.__timeout_role for r in user.roles):
            return True
        else:
            if self._timeouts.contains_user(user.id):
                # Clean up: User doesn't have timeout role but is still in 
                # self._timeouts list: remove user from list
                self._timeouts.remove_user(user.id)
            return False

    async def update_broadcasts(self):
        for b in self.broadcasts:
            await b.update()

    def scrim_channel_config(self, channel) -> dict:
        settings = self.__defaults.copy()
        channel = self.scrim_channels.get(str(channel), dict())
        settings.update(channel)
        return settings

    def add_user_timeout(self, user_id, duration: timedelta, reason=None):
        self._timeouts.add_user(user_id, duration, reason)

    def remove_user_timeout(self, user_id, reason=None):
        self._timeouts.remove_user(user_id, reason)

    def get_user_timeout(self, user_id):
        """Get remaining timeout for a user or None."""
        return self._timeouts.time_remaining(user_id)

    async def add_timeout_role(self, user_id, reason=None):
        if self.__timeout_role is None:
            return
        dc_guild = self.bot.get_guild(int(self.id))
        member = await dc_guild.fetch_member(user_id)
        if member:
            role = Snowflake(self.__timeout_role)
            await member.add_roles(role, reason=reason)

    async def remove_timeout_role(self, user_id, reason=None):
        if not self.__timeout_role:
            return
        dc_guild = self.bot.get_guild(int(self.id))
        member = await dc_guild.fetch_member(user_id)
        if member:
            role = Snowflake(self.__timeout_role)
            await member.remove_roles(role, reason=reason)

    def on_member_update(self, before, after):
        if any(role.id == self.__timeout_role for role in before.roles) \
                and all(role.id != self.__timeout_role for role in after.roles):
            # timeout role was removed
            try:
                self.remove_user_timeout(after.id)
            except ValueError:
                pass

    def queue_task(self, coro) -> asyncio.Task:
        return self.bot.loop.create_task(coro)

    def queue_callable(self, function: Callable) -> Callable:
        async def inner():
            function()

        def queue():
            self.queue_task(inner())

        return queue

    def __queue_coroutine(self, function: Callable[..., Coroutine[Any, Any, Any]]) -> Callable:
        def queue():
            self.queue_task(function())

        return queue

    def has_overlapping_scrims(self, scrim: scrimbot.Scrim) -> bool:
        earliest = scrim.time - timedelta(hours=1)
        latest = scrim.time + timedelta(hours=1)
        for scrim_manager in self.scrim_managers:
            if earliest < scrim_manager.scrim.time < latest and \
                    scrim.scrim_channel == scrim_manager.scrim.scrim_channel:
                return True
        return False
