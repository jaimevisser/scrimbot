import logging
import math
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Callable

import discord
import pytz
from discord.commands import Option
from discord.commands.permissions import Permission
from discord.enums import SlashCommandOptionType, ChannelType

import discutils
from data import ScrimbotData
from mixed import Mixed

logging.basicConfig(level=logging.DEBUG)

bot = discord.Bot()
data = ScrimbotData()

mixeds = []

bot.initialised = False

enabled_guilds = data.guilds


def remove_mixed(m: Mixed):
    if m in mixeds:
        mixeds.remove(m)
    data.get_mixeds(m.guild).remove(m.data)
    data.sync()


async def create_mixed(guild: int, mixed_data: dict):
    return await Mixed.create(bot, guild, mixed_data, data.sync, remove_mixed)


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
@is_mod()
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Note")
):
    """Make a note in a users' log."""

    modchannel = await bot.fetch_channel(data.config[str(ctx.guild_id)]["modchannel"])

    data.get_notes(ctx.guild_id).append({
        "id": uuid.uuid4().hex[0:12],
        "user": name.id,
        "time": datetime.now(timezone.utc).timestamp(),
        "text": text,
        "author": ctx.author.id})
    data.sync()
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

    data.get_notes(ctx.guild_id).append({
        "id": uuid.uuid4().hex[0:12],
        "user": name.id,
        "time": datetime.now(timezone.utc).timestamp(),
        "text": text,
        "author": ctx.author.id,
        "warning": True})
    data.sync()
    all_warns = data.warnings(ctx.guild_id, name.id)
    await name.send(f"You have been warned by {ctx.author.mention}: {text}\n"
                    f"Your warning count is now at {len(all_warns)}")
    await modchannel.send(f"User {name.mention} has been warned by {ctx.author.mention}: {text}\n"
                          f"Their warning count is now at {len(all_warns)}")
    await ctx.respond("User warned", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
@is_mod()
async def rmlog(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        id: Option(str, "ID of the note/warning to remove")
):
    """Remove a single warning/note from a user"""
    toremove = None

    guildnotes = data.get_notes(ctx.guild_id)

    for note in guildnotes:
        if note['user'] == name.id and note["id"] == id:
            toremove = note

    if toremove is not None:
        guildnotes.remove(toremove)
        data.sync()
        await ctx.respond("Note/warn removed", ephemeral=True)
    else:
        await ctx.respond("No matching note/warn found", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
@is_mod()
async def log(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for")
):
    """Display the log of a user, will print the log in the current channel."""
    nothing_found = True
    output = ""

    async def parse():
        nonlocal output, nothing_found
        if nothing_found:
            output = f"**Log for {name}**" + output
        await ctx.respond(output)
        nothing_found = False

    for note in data.get_notes(ctx.guild_id):
        if note['user'] == name.id:
            author = await ctx.guild.fetch_member(note['author'])

            icon = ""
            if "warning" in note:
                icon = "⚠ "
            new = f"[{note['id']}] <t:{math.floor(note['time'])}:d> {author} {icon}: {note['text']}"

            if len(output) + len(new) > 1800:
                await parse()
                output = ""

            output += "\n" + new

    if len(output) > 0:
        await parse()

    if nothing_found:
        await ctx.respond(f"Nothing in the log for {name}")


@bot.slash_command(guild_ids=enabled_guilds)
async def scrim(
        ctx,
        time: Option(str, "Time (UK timezone) when the scrim will start, format must be 14:00")
):
    """Start a scrim in this channel."""
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
    data.get_mixeds(ctx.guild_id).append(mixedobj)
    data.sync()

    mixeds.append(await create_mixed(ctx.guild_id, mixedobj))

    await ctx.respond(f"Scrim created for {discutils.timestamp(mixedtime)} (your local time)", ephemeral=True)


bot.run(data.token)
