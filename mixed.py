import datetime

import pytz
from discord import Bot, Member

import discutils
from mixedview import MixedView

tzuk = pytz.timezone("Europe/London")


class Mixed:

    def __init__(self, bot: Bot, data: dict, sync):
        self.__sync = sync
        self.__data = data
        self.__bot = bot
        self.__size = 8

        self.id = data["thread"]

        self.time = datetime.datetime.fromtimestamp(data["utc"], tzuk)

        self.__view = MixedView(self)

    async def __init(self):
        self.__thread = await self.__bot.fetch_channel(self.id)
        self.__message = await self.__thread.fetch_message(self.__data["message"])

        await self.update()

    async def update(self):
        await self.__message.edit(content=await self.__generate_message(), view=self.__view)

    async def __generate_message(self):
        message = f"Mixed scrim at {discutils.timestamp(self.time)}"
        if self.__data["players"] and len(self.__data["players"]) > 0:
            pass

        return message

    async def join(self, user: Member):
        if not self.__data["players"]:
            self.__data["players"] = []

        if len(self.__data["players"]) < self.__size:
            self.__data["players"].append({})

    @classmethod
    async def create(cls, bot: Bot, data: dict, sync):
        mixed = Mixed(bot, data, sync)
        await mixed.__init()
        return mixed
