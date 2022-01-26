import asyncio
import json
import logging
import os

import discord
import pytz

import scrimbot


class Guild:

    def __init__(self, id: str, config: dict, bot: discord.Bot):
        self.id = str(id)
        self.config = config
        self.bot: discord.Bot = bot
        self.__log = self.__load_list("log")
        self.__scrims = self.__load_list("scrims")
        self.log = scrimbot.Log(self.__log, lambda: self.__sync(self.__log, "log"))
        self.mod_channel = None
        self.timezone = pytz.timezone(self.config["timezone"])
        self.scrims = []
        self.broadcasts: list[scrimbot.Broadcaster] = []
        self.mod_roles = set()
        for scrim in self.__scrims:
            self.__create_scrim(scrim)
        if "mod_role" in self.config:
            self.mod_roles = self.mod_roles.union({self.config["mod_role"]})
        if "mod_roles" in self.config:
            self.mod_roles = self.mod_roles.union(set(self.config["mod_roles"]))

    async def init(self):
        self.guildobj = await self.bot.fetch_guild(int(self.id))
        self.mod_channel = await self.fetch_mod_channel()

        scrims = self.scrims.copy()
        for scrim in scrims:
            try:
                await scrim.init()
            except Exception as error:
                logging.error(f"Unable to properly initialise scrim {scrim.id} due to {error}")

        self.__broadcast_channels = \
            set(s["broadcast_channel"] for s in self.config["scrim_channels"].values() if "broadcast_channel" in s)

        for b in self.__broadcast_channels:
            self.broadcasts.append(scrimbot.Broadcaster(b, self))

    async def fetch_mod_channel(self):
        if self.mod_channel is None:
            self.mod_channel = self.bot.get_channel(self.config["mod_channel"])
        if self.mod_channel is None:
            try:
                self.mod_channel = await self.bot.fetch_channel(self.config["mod_channel"])
            except discord.DiscordException as error:
                logging.error(f"Unable to properly load mod channel for guild {self.id} due to {error}")
        return self.mod_channel

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
        await (self.__create_scrim(data)).init()

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
