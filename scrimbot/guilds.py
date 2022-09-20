from typing import Union

import discord

import scrimbot


class Guilds:

    def __init__(self, bot: discord.Bot):
        self.__bot = bot
        self.__guilds: dict[str, scrimbot.Guild] = {}

    async def get(self, guild_id: Union[str, int]) -> scrimbot.Guild:
        if str(guild_id) not in self.__guilds:
            self.__guilds[str(guild_id)] = scrimbot.Guild(str(guild_id), self.__bot)
            await self.__guilds[str(guild_id)].init()
        return self.__guilds[str(guild_id)]
