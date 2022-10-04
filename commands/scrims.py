import logging
import math
import re
from datetime import timedelta, datetime, timezone

import discord
import pytz
from discord import Option, slash_command
from discord.ext.commands import Cog

import scrimbot
from scrimbot import tag, Guilds

_log = logging.getLogger(__name__)


class Scrim(Cog):

    def __init__(self, guilds: Guilds):
        self.guilds = guilds

    async def timezone_search(self, ctx: discord.AutocompleteContext):
        return [tz for tz in pytz.common_timezones if ctx.value.lower() in tz.lower()]

    @slash_command()
    async def scrim(self, ctx,
                    time: Option(str, "Time when the scrim will start, format must be 14:00, 14.00 or 1400"),
                    time_zone: Option(str, "Timezone, if your time is in another timezone then the server",
                                      autocomplete=timezone_search, required=False),
                    name: Option(str, "Give this scrim a name", required=False),
                    size: Option(int, "Number of players for this scrim, the default is 8", required=False)
                    ):
        """Start a scrim in this channel."""
        guild = await self.guilds.get(ctx.guild_id)

        await ctx.defer(ephemeral=True)

        if guild.is_on_timeout(ctx.author):
            await ctx.respond("Sorry buddy, you are on a timeout!", ephemeral=True)
            return

        match = re.match(r"([0-9]{1,2})[:.]?([0-9]{2})", str(time))

        if not match:
            await ctx.respond("Invalid time, format must be 14:00, 14.00 or 1400!", ephemeral=True)
            return

        scrim_hour, scrim_minute = match.groups()

        if int(scrim_hour) > 23 or int(scrim_minute) > 59:
            await ctx.respond("Invalid time.", ephemeral=True)
            return

        local_tz = guild.timezone if time_zone is None else pytz.timezone(time_zone)

        local_time = datetime.now(local_tz)
        scrim_time = local_time.replace(hour=int(scrim_hour), minute=int(scrim_minute), second=0, microsecond=0)

        if scrim_time < local_time:
            scrim_time += timedelta(days=1)

        scrim_time = scrim_time.astimezone(guild.timezone)
        scrim_hour = str(scrim_time.hour).rjust(2, '0')
        scrim_minute = str(scrim_minute).rjust(2, '0')

        scrim_timestamp = math.floor(scrim_time.timestamp())

        author: discord.User = ctx.author

        scrim_data = {"players": [],
                      "reserve": [],
                      "author": {"id": author.id,
                                 "name": author.display_name,
                                 "avatar": author.display_avatar.url},
                      "time": scrim_timestamp,
                      "scrim_channel": ctx.channel.id,
                      "thread": 0}

        if name is not None:
            scrim_data["name"] = name
        if size is not None:
            scrim_data["size"] = size

        scrim_obj = guild.create_scrim(scrim_data)

        async def respond(text):
            await ctx.respond(text)

        if guild.has_overlapping_scrims(scrim_obj):
            view = scrimbot.YesNoView()
            await ctx.respond("Your scrim would overlap with an existing scrim, are you sure you want to create it?",
                              view=view)
            await view.wait()
            respond = view.respond

            if not view.value:
                await respond("No scrim created")
                return

        message: discord.Message = await ctx.channel.send(scrim_obj.generate_header_message())

        scrimname = f" {name}" if name is not None else ""
        thread = await message.create_thread(name=f"{scrim_hour}.{scrim_minute}{scrimname}")
        content = await thread.send("Loading scrim ...")
        scrim_data["thread"] = thread.id
        scrim_data["message"] = content.id

        guild.create_scrim_manager(scrim_obj)

        await respond(f"Scrim created for {tag.time(scrim_time)} (your local time)")

    @slash_command(name="active-scrims")
    async def active_scrims(self, ctx):
        """Get a list of active scrims that haven't started yet (10 max)"""
        guild = await self.guilds.get(ctx.guild_id)

        scrims: list[scrimbot.ScrimManager] = guild.scrim_managers
        relevant_scrims: list[scrimbot.ScrimManager] = \
            list([s for s in scrims if s.scrim.time >= datetime.now(timezone.utc)])
        relevant_scrims.sort(key=lambda s: s.scrim.time)
        relevant_scrims = relevant_scrims[:10]

        if len(relevant_scrims) == 0:
            await ctx.respond("No scrims currently active", ephemeral=True)
            return

        embeds = list([s.create_rich_embed() for s in relevant_scrims])

        await ctx.respond(embeds=embeds, ephemeral=True)

    @slash_command(name="ping-scrim")
    async def scrim_ping(self, ctx,
                         text: Option(str, "Text to ping the scrim with")
                         ):
        """Ping all players in the scrim"""
        guild = await self.guilds.get(ctx.guild_id)
        scrim_manager = guild.get_scrim_manager(ctx.channel.id)

        if scrim_manager is None:
            await ctx.respond("Sorry, there is no (active) scrim in this channel.", ephemeral=True)
            return

        response, ephemeral = scrim_manager.ping(text, ctx.author.id)

        await ctx.respond(response, ephemeral=ephemeral)

    @slash_command()
    @discord.default_permissions(administrator=True)
    async def kick(self, ctx,
                   player: Option(discord.Member, "User you want to kick from this scrim."),
                   reason: Option(str, "Specify the reason for kicking the user from the scrim.", required=False)
                   ):
        """Kick a player out of a scrim"""
        guild = await self.guilds.get(ctx.guild_id)
        scrim_manager = guild.get_scrim_manager(ctx.channel.id)

        if scrim_manager is None:
            await ctx.respond("Sorry, there is no (active) scrim in this channel.", ephemeral=True)
            return
        if not scrim_manager.contains_player(player.id):
            await ctx.respond("The player is not signed up for this scrim.", ephemeral=True)
            return
        if scrim_manager.scrim.started and scrim_manager.scrim.contains_player(player.id):
            await ctx.respond("This scrim has already started. The player can not be removed anymore.", ephemeral=True,
                              delete_after=5)
            return

        await scrim_manager.leave(player)
        await ctx.respond("Player was removed from the scrim.", ephemeral=True)

        guild.log.add_kick(ctx.channel.id, player.id, ctx.author.id,
                           text=reason if reason else "No reason given")

        s = f"{player} was kicked from the scrim at {scrim_manager.scrim.time.isoformat()} by {ctx.author}."
        s += f" Reason: {reason}." if reason else ""
        _log.info(s)

    @slash_command(name="archive-scrim")
    @discord.default_permissions(administrator=True)
    async def archive_scrim(self, ctx):
        """Archive an open scrim thread"""
        guild = await self.guilds.get(ctx.guild_id)

        if not isinstance(ctx.channel, discord.Thread):
            await ctx.respond("This isn't a thread", ephemeral=True)
            return

        guild.queue_task(ctx.channel.archive())
        await ctx.respond("Scrim thread will be archived in a short while", ephemeral=True)
