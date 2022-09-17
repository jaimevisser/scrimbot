import json
import logging

import discord
from discord import Permissions, ApplicationContext
from discord.ext.commands import Cog

import scrimbot
from scrimbot.settings import ParseException

_log = logging.getLogger(__name__)


class Settings(Cog):

    def __init__(self, guilds: dict[int, scrimbot.Guild]):
        self.guilds = guilds

    settings = discord.SlashCommandGroup(
        name="settings",
        description="Scrimbot settings",
        default_member_permissions=Permissions(administrator=True))

    @settings.command(name="upload")
    async def upload(self, ctx: ApplicationContext):
        guild = self.guilds[ctx.guild_id]

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
            await ctx.send_followup("Thanks")
        except ParseException as err:
            await ctx.send_followup(str(err))

    @settings.command(name="download")
    async def download(self, ctx: ApplicationContext):
        guild = self.guilds[ctx.guild_id]

        settings = guild.settings.get_filename()

        file = discord.File(settings)
        await ctx.respond(file=file, content="Here you go!")
