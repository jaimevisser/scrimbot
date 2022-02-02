import asyncio
import json
import logging
import os
from typing import Optional

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
        self.__log = self.__load_list("log")
        self.__scrims = self.__load_list("scrims")
        self.log = scrimbot.Log(self.__log, lambda: self.__sync(self.__log, "log"))
        self.mod_channel: Optional[discord.TextChannel] = None
        self.timezone = pytz.timezone(self.config["timezone"])
        self.timezone_name = self.config["timezone"]
        self.scrims = []
        self.broadcasts: list[scrimbot.Broadcaster] = []
        self.mod_roles = set()
        self.invite: Optional[discord.Invite] = None
        self.__invite_channel: Optional[discord.TextChannel] = None
        for scrim in self.__scrims:
            self.__create_scrim(scrim)
        if "mod_role" in self.config:
            self.mod_roles = self.mod_roles.union({self.config["mod_role"]})
        if "mod_roles" in self.config:
            self.mod_roles = self.mod_roles.union(set(self.config["mod_roles"]))
        if "name" in self.config:
            self.name += " - " + self.config["name"]

    async def init(self):
        self.guildobj = await self.bot.fetch_guild(int(self.id))
        self.mod_channel = await self.fetch_mod_channel()

        if "name" not in self.config:
            self.name += " - " + self.guildobj.name

        scrims = self.scrims.copy()
        for scrim in scrims:
            try:
                await scrim.init()
            except Exception as error:
                _log.error(f"Unable to properly initialise scrim {scrim.id} due to {error}")

        broadcast_channels = \
            set(s["broadcast_channel"] for s in self.config["scrim_channels"].values() if "broadcast_channel" in s)

        for b in broadcast_channels:
            self.broadcasts.append(scrimbot.Broadcaster(b, self))

        for b in self.broadcasts:
            self.queue_task(b.update())

    async def fetch_mod_channel(self):
        if self.mod_channel is None:
            self.mod_channel = self.bot.get_channel(self.config["mod_channel"])
        if self.mod_channel is None:
            try:
                self.mod_channel = await self.bot.fetch_channel(self.config["mod_channel"])
            except discord.DiscordException as error:
                _log.error(f"{self.name}: Unable to properly load mod channel due to {error}")
        return self.mod_channel

    async def fetch_invite(self):
        vanity = await self.__fetch_vanity_invite()
        if vanity is not None:
            return vanity
        if self.__invite_channel is None:
            await self.__fetch_invite_channel()
        if self.__invite_channel is not None:
            try:
                invite = await self.__invite_channel.create_invite(max_uses=0, max_age=0, unique=False)
                return invite
            except discord.DiscordException as error:
                _log.error(
                    f"{self.name}: Unable create an invite for channel {self.__invite_channel.id} due to {error}")

    async def __fetch_vanity_invite(self):
        try:
            return await self.guildobj.vanity_invite()
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

    def __load_list(self, name: str) -> list:
        try:
            with open(f"data/{self.id}-{name}.json", 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print("data file not found, initialising")
            return []
        except:
            os.rename(f"data/{self.id}-{name}.json", f"data/bad-{self.id}-{name}.json")
            return []

    def __sync(self, data: list, name: str):
        with open(f"data/{self.id}-{name}.json", 'w') as jsonfile:
            json.dump(data, jsonfile)

    def __create_scrim(self, data: dict):
        from scrimbot.scrimmanager import ScrimManager
        scrim = ScrimManager(self, data, self.__sync_scrims, self.__remove_scrim)
        self.scrims.append(scrim)
        return scrim

    def __remove_scrim(self, scrim):
        if scrim in self.scrims:
            self.scrims.remove(scrim)
        if scrim.scrim.data in self.__scrims:
            self.__scrims.remove(scrim.scrim.data)
        self.__sync_scrims()

    def __sync_scrims(self):
        self.__sync(self.__scrims, "scrims")

    async def create_scrim(self, data: dict):
        self.__scrims.append(data)
        self.__sync_scrims()
        scrim = self.__create_scrim(data)
        self.queue_task(scrim.init())

    def is_on_timeout(self, user: discord.Member) -> bool:
        for r in user.roles:
            if r.id == self.config["timeout_role"]:
                return True
        return False

    async def update_broadcast(self):
        for b in self.broadcasts:
            await b.update()

    def scrim_channel_config(self, channnel):
        return self.config["scrim_channels"][str(channnel)]

    def queue_task(self, coro) -> asyncio.Task:
        return self.bot.loop.create_task(coro)
