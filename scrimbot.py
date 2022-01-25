import logging
import math
import re
from datetime import datetime, timedelta
from typing import Callable

import discord
from discord.commands import Option
from discord.commands.permissions import Permission
from discord.enums import SlashCommandOptionType, ChannelType

import scrimbot
from scrimbot import tag, Scrim

logging.basicConfig(level=logging.DEBUG)

bot = discord.Bot()
config = scrimbot.Config()

guilds = {}

bot.initialised = False

for g in config.guilds:
    guilds[g] = scrimbot.Guild(str(g), config.config[str(g)], bot)


async def init():
    for guild in guilds.values():
        await guild.init()


def is_mod():
    """a decorator to add moderator role permissions to slash commands"""

    def decorator(func: Callable):
        # Create __app_cmd_perms__
        if not hasattr(func, '__app_cmd_perms__'):
            func.__app_cmd_perms__ = []

        for guild in guilds.values():
            func.__app_cmd_perms__.append(Permission(int(guild.config["mod_role"]), 1, True, int(guild.id)))

        return func

    return decorator


@bot.event
async def on_ready():
    if not bot.initialised:
        bot.initialised = True
        await init()

        print("Bot initialised")


@bot.slash_command(guild_ids=config.guilds)
async def report(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to report"),
        text: Option(str, "Tell us what you want to report")
):
    """Send a message to the moderators"""
    guild = guilds[ctx.guild_id]

    if guild.log.daily_report_count(ctx.author.id) > guild.config["reports_per_day"]:
        await ctx.respond("You've sent too many reports in the past 24 hours, please wait a bit", ephemeral=True)
        return

    guild.log.add_report(ctx.channel.id, name.id, ctx.author.id, text)
    await guild.mod_channel.send(f"{ctx.author.mention} would like to report {name.mention} "
                                 f"in {ctx.channel.mention} for the following:\n{text}")
    await ctx.respond("Report sent", ephemeral=True)


@bot.slash_command(guild_ids=config.guilds)
@is_mod()
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Note")
):
    """Make a note in a users' log."""
    guild = guilds[ctx.guild_id]

    guild.log.add_note(name.id, ctx.author.id, text)
    await guild.mod_channel.send(f"User {name.mention} has had a note added by {ctx.author.mention}: {text}")
    await ctx.respond("Note added", ephemeral=True)


@bot.slash_command(guild_ids=config.guilds)
@is_mod()
async def warn(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Warning")
):
    """Warn a user. A DM will be sent to the user as well."""
    guild = guilds[ctx.guild_id]

    guild.log.add_warning(name.id, ctx.author.id, text)
    warn_count = guild.log.warning_count(name.id)
    message = "User warned"
    try:
        await name.send(f"You have been warned by {ctx.author.mention}: {text}\n"
                        f"Your warning count is now at {warn_count}")
    except discord.HTTPException:
        message = "Warning logged but couldn't send the user the warning"

    await guild.mod_channel.send(f"User {name.mention} has been warned by {ctx.author.mention}: {text}\n"
                                 f"Their warning count is now at {warn_count}")
    await ctx.respond(message, ephemeral=True)


@bot.slash_command(guild_ids=config.guilds)
@is_mod()
async def rmlog(
        ctx,
        id: Option(str, "ID of the entry to remove, it's the gibberish in square brackets [] in the log")
):
    """Remove a single log entry from a user"""
    guild = guilds[ctx.guild_id]

    num_removed = guild.log.remove(predicate=lambda entry: entry["id"] == id)

    if num_removed > 0:
        await ctx.respond("Entry removed", ephemeral=True)
    else:
        await ctx.respond("No matching entries found", ephemeral=True)


@bot.slash_command(guild_ids=config.guilds)
@is_mod()
async def purgelog(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to clear the log for")
):
    """Remove everything in the log for a user"""
    guild = guilds[ctx.guild_id]

    num_removed = guild.log.remove(predicate=lambda entry: entry["user"] == name.id)

    if num_removed > 0:
        await guild.mod_channel.send(f"{ctx.author.mention} purged the log of {name.mention}.")
        await ctx.respond("Matching entries removed", ephemeral=True)
    else:
        await ctx.respond("No matching entries found", ephemeral=True)


@bot.slash_command(guild_ids=config.guilds)
@is_mod()
async def log(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to display the log for")
):
    """Display the log of a user, will print the log in the current channel."""
    guild = guilds[ctx.guild_id]
    types = None
    authors = False

    if ctx.channel.id == guild.mod_channel.id:
        types = scrimbot.Log.ALL
        authors = True

    entries = guild.log.print_log(name.id, types=types, authors=authors)

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


@bot.slash_command(guild_ids=config.guilds)
async def scrim(
        ctx,
        time: Option(str, "Time when the scrim will start, format must be 14:00, 14.00 or 1400")
):
    """Start a scrim in this channel."""
    guild = guilds[ctx.guild_id]

    if guild.is_on_timeout(ctx.author):
        await ctx.respond("Sorry buddy, you are on a timeout!", ephemeral=True)
        return

    match = re.match("([0-9]{1,2})[:.]?([0-9]{2})", str(time))

    if not match:
        await ctx.respond("Invalid time, format must be 14:00, 14.00 or 1400!", ephemeral=True)
        return

    if str(ctx.channel.id) not in guild.config["scrim_channels"].keys():
        await ctx.respond("This is not a channel for organising scrims!", ephemeral=True)
        return

    scrim_hour, scrim_minute = match.groups()

    if int(scrim_hour) > 23 or int(scrim_minute) > 59:
        await ctx.respond("Invalid time.", ephemeral=True)
        return

    await ctx.defer(ephemeral=True)

    guild_time = datetime.now(guild.timezone)
    scrim_time = guild_time.replace(hour=int(scrim_hour), minute=int(scrim_minute), second=0, microsecond=0)

    if scrim_time < guild_time:
        scrim_time += timedelta(days=1)

    scrim_timestamp = math.floor(scrim_time.timestamp())
    channel_config = guild.scrim_channel_config(ctx.channel.id)
    scrimmer_role = channel_config["role"]

    author: discord.User = ctx.author

    scrim_data = {"players": [],
                  "reserve": [],
                  "role": scrimmer_role,
                  "author": {"id": author.id,
                             "name": author.display_name,
                             "avatar": author.display_avatar.url},
                  "time": scrim_timestamp,
                  "thread": 0}

    scrim = Scrim(scrim_data, guild.timezone, None)

    message = await ctx.channel.send(scrim.generate_header_message())

    thread = await ctx.channel.create_thread(message=message, name=f"{scrim_hour}.{scrim_minute}",
                                             type=ChannelType.public_thread)
    scrim_data["thread"] = thread.id
    content = await thread.send(scrim.generate_content_message())
    scrim_data["message"] = content.id

    await guild.create_scrim(scrim_data)

    await ctx.respond(f"Scrim created for {tag.time(scrim_time)} (your local time)", ephemeral=True)


bot.run(config.token)
