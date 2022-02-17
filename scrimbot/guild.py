import asyncio
import logging
from typing import Optional, Callable

import discord
import pytz

import scrimbot

_log = logging.getLogger(__name__)


class Guild:

    def __init__(self, id: str, config: dict, bot: discord.Bot):
        self.id = str(id)
        self.name = str(id)
        self.config = config
        self.bot: discord.Bot = bot
        self.__log = scrimbot.Store[list](f"data/{self.id}-log.json", [])
        self.__scrims = scrimbot.Store[list](f"data/{self.id}-scrims.json", [])
        self.log = scrimbot.Log(self.__log.data, self.queue_callable(self.__log.sync))
        self.mod_channel: Optional[discord.TextChannel] = None
        self.timezone = pytz.timezone(self.config["timezone"])
        self.scrim_managers: list[scrimbot.ScrimManager] = []
        self.broadcasts: list[scrimbot.Broadcaster] = []
        self.mod_roles = set()
        self.invite: Optional[discord.Invite] = None
        self.__invite_channel: Optional[discord.TextChannel] = None
        self.__guild: Optional[discord.Guild] = None
        self.__timeout_role = self.config.get("scrim", dict()).get("timeout_role", None)

        self.__defaults = self.config.get("scrim", dict()).copy()
        self.__defaults.pop("channels", None)

        for scrim in self.__scrims.data:
            self.__create_scrim(scrim)
        if "mod_role" in self.config:
            self.mod_roles = self.mod_roles.union({self.config["mod_role"]})
        if "mod_roles" in self.config:
            self.mod_roles = self.mod_roles.union(set(self.config["mod_roles"]))
        if "name" in self.config:
            self.name += " - " + self.config["name"]

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

    def __create_scrim(self, data: dict) -> "scrimbot.ScrimManager":
        scrim = self.create_scrim(data)
        return self.__create_scrim_manager(scrim)

    def create_scrim(self, data: dict) -> scrimbot.Scrim:
        return scrimbot.Scrim(data, self.timezone, self.queue_callable(self.__scrims.sync))

    def __create_scrim_manager(self, scrim) -> "scrimbot.ScrimManager":
        from scrimbot.scrimmanager import ScrimManager
        scrim_manager = ScrimManager(self, scrim, self.__remove_scrim)
        self.scrim_managers.append(scrim_manager)
        return scrim_manager

    def get_scrim_manager(self, id: int) -> "scrimbot.ScrimManager":
        return next(filter(lambda s: s.id == id, self.scrim_managers), None)

    def __remove_scrim(self, scrim):
        if scrim in self.scrim_managers:
            self.scrim_managers.remove(scrim)
        if scrim.scrim.data in self.__scrims.data:
            self.__scrims.data.remove(scrim.scrim.data)
        self.queue_callable(self.__scrims.sync)()

    def create_scrim_manager(self, scrim: scrimbot.Scrim):
        self.__scrims.data.append(scrim.data)
        self.queue_callable(self.__scrims.sync)()
        scrim = self.__create_scrim_manager(scrim)
        self.queue_task(scrim.init())

    def is_on_timeout(self, user: discord.Member) -> bool:
        for r in user.roles:
            if r.id == self.__timeout_role:
                return True
        return False

    async def update_broadcasts(self):
        for b in self.broadcasts:
            await b.update()

    def scrim_channel_config(self, channel) -> dict:
        settings = self.__defaults.copy()
        channel = self.scrim_channels[str(channel)]
        settings.update(channel)
        return settings

    def queue_task(self, coro) -> asyncio.Task:
        return self.bot.loop.create_task(coro)

    def queue_callable(self, function: Callable) -> Callable:
        async def inner():
            function()

        def queue():
            self.queue_task(inner())

        return queue
