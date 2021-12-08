import json
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
    if str(guild) not in data:
        data[str(guild)] = {}
    if "notes" not in data[guild]:
        data[guild]["notes"] = []
    return data[guild]["notes"]


@bot.slash_command(guild_ids=[908282497769558036])
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        note: Option(str, "Note")
):
    get_notes(ctx.guild_id).append({"user": name.id, "time": datetime.now(timezone.utc).timestamp(), "note": note})
    sync()
    await ctx.respond("Note added", ephemeral=True)


bot.run(token)
