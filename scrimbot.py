import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

import discord

import commands
import scrimbot
from scrimbot import tag, Config

os.makedirs("data/logs", exist_ok=True)
filehandler = RotatingFileHandler(filename="data/logs/scrimbot.log", mode="w", maxBytes=1024 * 50, backupCount=4)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s:%(message)s",
                    handlers=[filehandler])

# members intent needed for on_member_update() event
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Bot(intents=intents)

guilds = scrimbot.Guilds(bot)

oculus_profiles = scrimbot.OculusProfiles(bot, guilds=guilds)
bot.oculus_profiles = oculus_profiles
bot.initialised = False

_log = logging.getLogger("scrimbot")


async def init():
    for guild in guilds.values():
        try:
            await guild.init()
        except Exception as error:
            _log.error(f"Unable to properly initialise guild {guild.name} due to {error}")
            _log.exception(error)


@bot.event
async def on_ready():
    if not bot.initialised:
        bot.initialised = True
        _log.info("Bot initialised")


@bot.slash_command()
async def time(ctx):
    """Show server time"""
    guild = await guilds.get(ctx.guild_id)

    server_time = datetime.now(guild.timezone)

    await ctx.respond(f"**Server timezone**\n"
                      f"{guild.timezone.zone}\n"
                      f"**Server time**\n"
                      f"{server_time.strftime('%H:%M')}\n"
                      f"**Discord time tag**\n"
                      f"{tag.time(server_time)}", ephemeral=True)


@bot.event
async def on_member_update(before, after):
    guild = await guilds.get(after.guild.id)
    guild.on_member_update(before, after)


bot.add_cog(commands.Moderation(guilds))
bot.add_cog(commands.Scrim(guilds))
bot.add_cog(commands.Oculus(guilds, oculus_profiles))
bot.add_cog(commands.TimeoutList(guilds))
bot.add_cog(commands.Settings(guilds))

bot.run(Config().token)
