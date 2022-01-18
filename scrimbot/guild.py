import json
import os

import discord
import pytz

import scrimbot


class Guild:

    def __init__(self, id: str, config: dict, bot: discord.Bot):
        self.id = str(id)
        self.config = config
        self.bot = bot
        self.__log = self.__load_list("log")
        self.__scrims = self.__load_list("scrims")
        self.log = scrimbot.Log(self.__log, lambda: self.__sync(self.__log, "log"))
        self.mod_channel = None
        self.timezone = pytz.timezone(self.config["timezone"])
        self.scrims = []
        for scrim in self.__scrims:
            self.__create_scrim(scrim)

    async def init(self):
        self.mod_channel = await self.bot.fetch_channel(self.config["mod_channel"])

        for scrim in self.scrims:
            await scrim.init()

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
        self.scrims.remove(scrim)
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
