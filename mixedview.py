from typing import Optional

import discord
from discord import ButtonStyle, Interaction


class MixedButton(discord.ui.Button):
    def __init__(self,
                 style: ButtonStyle = ButtonStyle.secondary,
                 label: Optional[str] = None,
                 custom_id: Optional[str] = None,
                 callback_func=None
                 ):
        super().__init__(style=style, label=label, custom_id=custom_id)
        self.__callback_func = callback_func

    async def callback(self, interaction: Interaction):
        if self.__callback_func is None:
            return
        await self.__callback_func(interaction)


class MixedView(discord.ui.View):
    def __init__(self, custom_id: str):
        super().__init__(timeout=None)
        self.__custom_id = custom_id

        self.add_item(MixedButton(
            label="Join", style=discord.ButtonStyle.green, custom_id=custom_id + ":join", callback_func=self.join))
        self.add_item(MixedButton(
            label="Reserve", style=discord.ButtonStyle.blurple, custom_id=custom_id + ":reserve",
            callback_func=self.reserve))
        self.add_item(MixedButton(
            label="Leave", style=discord.ButtonStyle.red, custom_id=custom_id + ":leave", callback_func=self.leave))

    async def join(self, interaction: discord.Interaction):
        await interaction.response.send_message("Added you to the mixed.", ephemeral=True)

    async def reserve(self, interaction: discord.Interaction):
        await interaction.response.send_message("Put you on the reserve list.", ephemeral=True)

    async def leave(self, interaction: discord.Interaction):
        await interaction.response.send_message("Removed you from the mixed.", ephemeral=True)
