import logging
import math
import re
from datetime import datetime, timedelta
from typing import Callable

import discord
import pytz
from discord import HTTPException
from discord.commands import Option
from discord.commands.permissions import Permission
from discord.enums import SlashCommandOptionType, ChannelType

import discutils
from data import ScrimbotData
from log import Log
from mixed import Mixed

logging.basicConfig(level=logging.DEBUG)

bot = discord.Bot()
data = ScrimbotData()
bot_log = Log(data.get_log, data.sync)

mixeds = []

bot.initialised = False

enabled_guilds = data.guilds


def remove_mixed(m: Mixed):
    if m in mixeds:
        mixeds.remove(m)
    data.get_mixeds(m.guild).remove(m.data)
    data.sync()


async def create_mixed(guild: int, mixed_data: dict):
    return await Mixed.create(bot, guild, mixed_data, data, data.sync, remove_mixed)


def is_mod():
    """a decorator to add moderator role permissions to slash commands"""

    def decorator(func: Callable):
        # Create __app_cmd_perms__
        if not hasattr(func, '__app_cmd_perms__'):
            func.__app_cmd_perms__ = []

        for guild in data.guilds:
            func.__app_cmd_perms__.append(Permission(int(data.config[str(guild)]["modrole"]), 1, True, guild))

        return func

    return decorator


@bot.event
async def on_ready():
    if not bot.initialised:

        bot.initialised = True
        for guild in enabled_guilds:
            for mixed_data in data.get_mixeds(guild):
                mixeds.append(await create_mixed(guild, mixed_data))

        print("Bot initialised")


@bot.slash_command(guild_ids=enabled_guilds)
async def report(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to report"),
        text: Option(str, "Tell us what you want to report")
):
    """Send a message to the moderators"""
    modchannel = await bot.fetch_channel(data.config[str(ctx.guild_id)]["modchannel"])

    await modchannel.send(f"{ctx.author.mention} would like to report {name.mention} "
                          f"in {ctx.channel.mention} for the following:\n{text}")
    await ctx.respond("Report sent", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
@is_mod()
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Note")
):
    """Make a note in a users' log."""

    modchannel = await bot.fetch_channel(data.config[str(ctx.guild_id)]["modchannel"])
    bot_log.add_note(ctx.guild_id, name.id, ctx.author.id, text)
    await modchannel.send(f"User {name.mention} has had a note added by {ctx.author.mention}: {text}")
    await ctx.respond("Note added", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
@is_mod()
async def warn(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Warning")
):
    """Warn a user. A DM will be sent to the user as well."""

    modchannel = await bot.fetch_channel(data.config[str(ctx.guild_id)]["modchannel"])
    bot_log.add_warning(ctx.guild_id, name.id, ctx.author.id, text)
    warn_count = bot_log.warning_count(ctx.guild_id, name.id)
    message = "User warned"
    try:
        await name.send(f"You have been warned by {ctx.author.mention}: {text}\n"
                        f"Your warning count is now at {warn_count}")
    except HTTPException:
        message = "Warning logged but couldn't send the user the warning"

    await modchannel.send(f"User {name.mention} has been warned by {ctx.author.mention}: {text}\n"
                          f"Their warning count is now at {warn_count}")
    await ctx.respond(message, ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
@is_mod()
async def rmlog(
        ctx,
        id: Option(str, "ID of the entry to remove, it's the gibberish in square brackets [] in the log")
):
    """Remove a single log entry from a user"""

    num_removed = bot_log.remove(ctx.guild_id, predicate=lambda entry: entry["id"] == id)

    if num_removed > 0:
        await ctx.respond("Entry removed", ephemeral=True)
    else:
        await ctx.respond("No matching entries found", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
@is_mod()
async def purgelog(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to clear the log for")
):
    """Remove everything in the log for a user"""
    modchannel = await bot.fetch_channel(data.config[str(ctx.guild_id)]["modchannel"])
    num_removed = bot_log.remove(ctx.guild_id, predicate=lambda entry: entry["user"] == name.id)

    if num_removed > 0:
        await modchannel.send(f"{ctx.author.mention} purged the log of {name.mention}.")
        await ctx.respond("Matching entries removed", ephemeral=True)
    else:
        await ctx.respond("No matching entries found", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
@is_mod()
async def log(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to display the log for")
):
    """Display the log of a user, will print the log in the current channel."""
    types = None
    authors = False

    if ctx.channel.id == data.config[str(ctx.guild_id)]["modchannel"]:
        types = Log.ALL
        authors = True

    entries = bot_log.print_log(ctx.guild_id, name.id, types = types, authors = authors)

    if len(entries) == 0:
        await ctx.respond(f"Nothing in the log for {name}")
        return

    output = f"**Log for {name}**"

    for entry in entries:
        if len(output + entry) > 1800:
            await ctx.respond(output)
            output = entry
        else:
            output += "\n" + entry
    await ctx.respond(output)


@bot.slash_command(guild_ids=enabled_guilds)
async def scrim(
        ctx,
        time: Option(str, "Time (UK timezone) when the scrim will start, format must be 14:00")
):
    """Start a scrim in this channel."""
    if discutils.has_role(ctx.author, data.config[str(ctx.guild_id)]["timeoutrole"]):
        await ctx.respond("Sorry buddy, you are on a timeout!", ephemeral=True)
        return

    match = re.match("([0-9]{1,2}):?([0-9]{2})", str(time))

    mixedobj = {"players": [], "reserves": []}

    if not match:
        await ctx.respond("Invalid time, format must be 14:00!", ephemeral=True)
        return

    if not ctx.channel.id in map(lambda x: int(x), data.config[str(ctx.guild_id)]["mixedchannels"].keys()):
        await ctx.respond("This is not a channel for organising scrims!", ephemeral=True)
        return

    scrimmer_role = data.config[str(ctx.guild_id)]["mixedchannels"][str(ctx.channel.id)]["role"]

    mixedhour, mixedminutes = match.groups()

    if int(mixedhour) > 23 or int(mixedminutes) > 59:
        await ctx.respond("Invalid time.", ephemeral=True)
        return

    uknow = datetime.now(pytz.timezone("Europe/London"))
    mixedtime = uknow.replace(hour=int(mixedhour), minute=int(mixedminutes), second=0, microsecond=0)

    if mixedtime < uknow:
        mixedtime += timedelta(days=1)

    mixed_utc = math.floor(mixedtime.timestamp())

    mixedobj["utc"] = mixed_utc

    thread = await ctx.channel.create_thread(name=f"{mixedhour}{mixedminutes}", type=ChannelType.public_thread)

    mixedobj["thread"] = thread.id
    message = await thread.send(f"Scrim at {discutils.timestamp(mixedtime)}")
    mixedobj["message"] = message.id
    mixedobj["role"] = scrimmer_role
    mixedobj["creator"] = ctx.author.id
    data.get_mixeds(ctx.guild_id).append(mixedobj)
    data.sync()

    mixeds.append(await create_mixed(ctx.guild_id, mixedobj))

    await ctx.respond(f"Scrim created for {discutils.timestamp(mixedtime)} (your local time)", ephemeral=True)


bot.run(data.token)
