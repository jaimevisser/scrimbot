import json
import logging

import discord
from discord import Permissions, ApplicationContext
from discord.ext.commands import Cog

from scrimbot import Guilds
from scrimbot.settings import ParseException

_log = logging.getLogger(__name__)


class Settings(Cog):

    def __init__(self, guilds: Guilds):
        self.guilds = guilds

    settings = discord.SlashCommandGroup(
        name="settings",
        description="Scrimbot settings",
        default_member_permissions=Permissions(administrator=True))

    @settings.command(name="upload")
    async def upload(self, ctx: ApplicationContext):
        """Upload a new settings file for your discord guild."""
        guild = await self.guilds.get(ctx.guild_id)

        await ctx.respond("Send a message with the settings file attached in this channel in the next minute")

        def from_same_author(m: discord.Message):
            return m.author == ctx.author

        try:
            response: discord.Message = await guild.bot.wait_for("message", check=from_same_author, timeout=60)
        except TimeoutError:
            return await ctx.send_followup("Sorry, you took too long. I stopped listening.")

        if response.attachments.count() != 1:
            return await ctx.send_followup("I need a single file, I don't know what to do with this")

        data = json.loads(await response.attachments.pop().read())

        try:
            guild.settings.replace(data)
            await ctx.send_followup("Thanks, reloading guild now.")
            await guild.reload()
            await ctx.send_followup("Your settings have been applied and your guild has been reloaded.")
        except ParseException as err:
            await ctx.send_followup(str(err))

    @settings.command(name="download")
    async def download(self, ctx: ApplicationContext):
        """Download the settings file for your discord guild."""
        guild = await self.guilds.get(ctx.guild_id)

        settings = guild.settings.get_filename()

        file = discord.File(settings)
        await ctx.respond(file=file, content="Here you go!", ephemeral=True)

    @settings.command(name="reload")
    async def reload(self, ctx: ApplicationContext):
        """Reload the stored settings and partially re-initialise your guild."""
        guild = await self.guilds.get(ctx.guild_id)
        await ctx.respond("Reloading...", ephemeral=True)
        await guild.reload()
        await ctx.send_followup("Your guild has been reloaded.", ephemeral=True)
