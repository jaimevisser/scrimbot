
import math
from datetime import datetime, timezone

import discord
from discord.enums import SlashCommandOptionType, ChannelType
from discord.commands import Option

from data import ScrimbotData

bot = discord.Bot()
data = ScrimbotData()


@bot.slash_command(guild_ids=[908282497769558036])
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Note")
):
    data.get_notes(ctx.guild_id).append({
        "user": name.id,
        "time": datetime.now(timezone.utc).timestamp(),
        "text": text,
        "author": ctx.author.id})
    data.sync()
    await ctx.respond("Note added", ephemeral=True)


@bot.slash_command(guild_ids=[908282497769558036])
async def warn(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Warning")
):
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


@bot.slash_command(guild_ids=[908282497769558036])
async def log(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for")
):
    nothing_found = True
    output = ""

    for note in data.get_notes(ctx.guild_id):
        if note['user'] == name.id:
            icon = ""
            if "warning" in note:
                icon = "⚠ "
            new = f"<t:{math.floor(note['time'])}:d> {icon}: {note['text']}"

            if len(output) + len(new) > 2000:
                await ctx.respond(output)
                nothing_found = False
                output = ""

            output += "\n" + new

    if len(output) > 0:
        await ctx.respond(output)
        nothing_found = False

    if nothing_found:
        await ctx.respond("Nothing in the log")


@bot.slash_command(guild_ids=[908282497769558036])
async def mixed(
        ctx):
    thread = await ctx.channel.create_thread(name="example thread", type=ChannelType.public_thread)

    await ctx.respond("Mixed created", ephemeral=True)


bot.run(data.token)
