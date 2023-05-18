import logging
from typing import Union

import discord

import scrimbot
from scrimbot import ScrimManager

_log = logging.getLogger(__name__)


class Guilds:

    def __init__(self, bot: discord.Bot):
        self.__bot = bot
        self.__guilds: dict[str, scrimbot.Guild] = {}
        bot.scrim_overlap_check = self.get_overlapping_scrim_managers

    async def get(self, guild_id: Union[str, int]) -> scrimbot.Guild:
        if str(guild_id) not in self.__guilds:
            _log.info(f"Creating guild {guild_id}")
            self.__guilds[str(guild_id)] = scrimbot.Guild(str(guild_id), self.__bot)
            await self.__guilds[str(guild_id)].init()
            _log.info(f"Guild {guild_id} initialised")
        return self.__guilds[str(guild_id)]

    def get_overlapping_scrim_managers(self, user: int, scrim_manager: ScrimManager) -> list[ScrimManager]:
        scrim_managers = [sm for guild in self.__guilds.values()
                          for sm in guild.scrim_managers
                          if sm is not scrim_manager
                          and sm.contains_player(user)
                          and sm.scrim.overlaps_with(scrim_manager.scrim)]
        return scrim_managers
