import json
import math
import os
from datetime import datetime, timezone

import discord
from discord.enums import SlashCommandOptionType
from discord.commands import Option

with open('bot.token', 'r') as file:
    token = file.read().strip()

try:
    with open('data.json', 'r') as file:
        data = json.load(file)
except FileNotFoundError:
    print("data file not found, initialising")
    data = {}
except:
    os.rename('data.json', 'baddata.json')
    data = {}

bot = discord.Bot()


def sync():
    with open('data.json', 'w') as jsonfile:
        json.dump(data, jsonfile)


def get_notes(guild) -> list:
    guild = str(guild)
    if guild not in data:
        data[guild] = {}
    if "notes" not in data[guild]:
        data[guild]["notes"] = []
    return data[guild]["notes"]


def warnings(guild, member):
    return [d for d in get_notes(guild) if 'warning' in d and d['user'] == member]


@bot.slash_command(guild_ids=[908282497769558036])
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Note")
):
    get_notes(ctx.guild_id).append({
        "user": name.id,
        "time": datetime.now(timezone.utc).timestamp(),
        "text": text,
        "author": ctx.author.id})
    sync()
    await ctx.respond("Note added", ephemeral=True)


@bot.slash_command(guild_ids=[908282497769558036])
async def warn(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Warning")
):
    get_notes(ctx.guild_id).append({
        "user": name.id,
        "time": datetime.now(timezone.utc).timestamp(),
        "text": text,
        "author": ctx.author.id,
        "warning": True})
    sync()
    all_warns = warnings(ctx.guild_id, name.id)
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

    for note in get_notes(ctx.guild_id):
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

bot.run(token)
