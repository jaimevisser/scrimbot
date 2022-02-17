import logging
from typing import Optional

import discord

import scrimbot

_log = logging.getLogger(__name__)


class ScrimButton(discord.ui.Button):
    def __init__(self,
                 style: discord.ButtonStyle = discord.ButtonStyle.secondary,
                 label: Optional[str] = None,
                 custom_id: Optional[str] = None,
                 callback_func=None
                 ):
        super().__init__(style=style, label=label, custom_id=custom_id)
        self.__callback_func = callback_func

    async def callback(self, interaction: discord.Interaction):
        try:
            if self.__callback_func is None:
                return
            await self.__callback_func(interaction)
        except Exception as err:
            _log.error("Error during interaction with button.")
            _log.exception(err)
            await interaction.response.send_message(
                "Something went terribly wrong but it has been logged.", ephemeral=True)


class ScrimView(discord.ui.View):
    def __init__(self, scrim: scrimbot.ScrimManager):
        super().__init__(timeout=None)
        self.__scrim = scrim
        custom_id = str(scrim.id)
        self.use = "before"

        self.__button_join = ScrimButton(
            label="Join", style=discord.ButtonStyle.green, custom_id=custom_id + ":join", callback_func=self.join)
        self.__button_reserve = ScrimButton(
            label="Reserve", style=discord.ButtonStyle.blurple, custom_id=custom_id + ":reserve",
            callback_func=self.reserve)
        self.__button_leave = ScrimButton(
            label="Leave", style=discord.ButtonStyle.red, custom_id=custom_id + ":leave", callback_func=self.leave)

        self.add_item(self.__button_join)
        self.add_item(self.__button_reserve)
        self.add_item(self.__button_leave)

    async def join(self, interaction: discord.Interaction):
        response = await self.__scrim.join(interaction.user)
        await interaction.response.send_message(response, ephemeral=True)

    async def reserve(self, interaction: discord.Interaction):
        response = await self.__scrim.reserve(interaction.user)
        await interaction.response.send_message(response, ephemeral=True)

    async def leave(self, interaction: discord.Interaction):
        await self.__scrim.leave(interaction.user)
        await interaction.response.send_message("Removed you from the scrim.", ephemeral=True)


class ScrimRunningView(discord.ui.View):
    def __init__(self, scrim: scrimbot.ScrimManager):
        super().__init__(timeout=None)
        self.__scrim = scrim
        custom_id = str(scrim.id)
        self.use = "running"

        self.__button_reserve = ScrimButton(
            label="Reserve", style=discord.ButtonStyle.blurple, custom_id=custom_id + ":reserve",
            callback_func=self.reserve)
        self.__button_call_reserve = ScrimButton(
            label="Call reserve", style=discord.ButtonStyle.gray, custom_id=custom_id + ":call",
            callback_func=self.call_reserve)

        self.add_item(self.__button_reserve)
        self.add_item(self.__button_call_reserve)

    async def reserve(self, interaction: discord.Interaction):
        response = await self.__scrim.reserve(interaction.user)
        await interaction.response.send_message(response, ephemeral=True)

    async def call_reserve(self, interaction: discord.Interaction):
        if not self.__scrim.contains_player(interaction.user.id):
            await interaction.response.send_message("You aren't in the scrim, buddy", ephemeral=True)
            return

        response, ephemeral = await self.__scrim.call_reserve()
        await interaction.response.send_message(response, ephemeral=ephemeral)
