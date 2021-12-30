import logging
import math
import re
from datetime import datetime, timezone, timedelta

import discord
import pytz
from discord.enums import SlashCommandOptionType, ChannelType
from discord.commands import Option

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


async def create_mixed(guild, mixed_data: dict):
    return await Mixed.create(bot, guild, mixed_data, data.sync, remove_mixed)


@bot.event
async def on_ready():
    if not bot.initialised:
        bot.initialised = True
        for guild in enabled_guilds:
            for mixed_data in data.get_mixeds(guild):
                mixeds.append(await create_mixed(guild, mixed_data))

        print("Bot initialised")


@bot.slash_command(guild_ids=enabled_guilds)
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Note")
):
    """Make a note in a users' log."""
    data.get_notes(ctx.guild_id).append({
        "user": name.id,
        "time": datetime.now(timezone.utc).timestamp(),
        "text": text,
        "author": ctx.author.id})
    data.sync()
    await ctx.respond("Note added", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
async def warn(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Warning")
):
    """Warn a user. A DM will be sent to the user as well."""
    data.get_notes(ctx.guild_id).append({
        "user": name.id,
        "time": datetime.now(timezone.utc).timestamp(),
        "text": text,
        "author": ctx.author.id,
        "warning": True})
    data.sync()
    all_warns = data.warnings(ctx.guild_id, name.id)
    await name.send(f"You have been warned by {ctx.author.mention}: {text}")
    await name.send(f"Your warning count is now at {len(all_warns)}")
    await ctx.respond("User warned", ephemeral=True)


@bot.slash_command(guild_ids=enabled_guilds)
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
            icon = ""
            if "warning" in note:
                icon = "⚠ "
            new = f"<t:{math.floor(note['time'])}:d> {icon}: {note['text']}"

            if len(output) + len(new) > 1800:
                await parse()
                output = ""

            output += "\n" + new

    if len(output) > 0:
        await parse()

    if nothing_found:
        await ctx.respond("Nothing in the log")


@bot.slash_command(guild_ids=enabled_guilds)
async def mixed(
        ctx,
        time: Option(str, "Time (UK timezone) when the mixed will start, format must be 14:00")
):
    """Start a mixed game in this channel."""
    match = re.match("([0-9]{1,2}):?([0-9]{2})", str(time))

    mixedobj = {"players": [], "reserves": []}

    if not match:
        await ctx.respond("Invalid time, format must be 14:00", ephemeral=True)
        return

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
    data.get_mixeds(ctx.guild_id).append(mixedobj)
    data.sync()

    mixeds.append(await create_mixed(ctx.guild_id, mixedobj))

    await ctx.respond(f"Mixed created for {discutils.timestamp(mixedtime)} (your local time)", ephemeral=True)


bot.run(data.token)
