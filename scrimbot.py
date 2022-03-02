import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from typing import Callable

import discord
from discord import CommandPermission
from discord.commands import Option
from discord.enums import SlashCommandOptionType

import scrimbot
from scrimbot import tag

os.makedirs("data/logs", exist_ok=True)
filehandler = RotatingFileHandler(filename="data/logs/scrimbot.log", mode="w", maxBytes=1024 * 50, backupCount=4)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s:%(message)s",
                    handlers=[filehandler])

# members intent needed for on_member_update() event
intents = discord.Intents.default()
intents.members = True

bot = discord.Bot(intents=intents)
config = scrimbot.Config()
oculus_profiles = scrimbot.OculusProfiles(bot)

guilds = {}

bot.oculus_profiles = oculus_profiles
bot.initialised = False

_log = logging.getLogger("scrimbot")

MOD_PERMISSIONS = []

for g in config.guilds:
    guilds[g] = scrimbot.Guild(str(g), config.config[str(g)], bot)

for guild in guilds.values():
    for role in guild.mod_roles:
        MOD_PERMISSIONS.append(CommandPermission(int(role), 1, True, int(guild.id)))


async def init():
    for guild in guilds.values():
        try:
            await guild.init()
        except Exception as error:
            _log.error(f"Unable to properly initialise guild {guild.name} due to {error}")
            _log.exception(error)


def is_mod():
    """a decorator to add moderator role permissions to slash commands"""

    def decorator(func: Callable):
        # Create __app_cmd_perms__
        if not hasattr(func, '__app_cmd_perms__'):
            func.__app_cmd_perms__ = []

        for guild in guilds.values():
            for role in guild.mod_roles:
                func.__app_cmd_perms__.append(CommandPermission(int(role), 1, True, int(guild.id)))

        return func

    return decorator


@bot.event
async def on_ready():
    if not bot.initialised:
        bot.initialised = True
        await init()

        _log.info("Bot initialised")


@bot.slash_command(guild_ids=config.guilds_with_features({"LOG", "REPORT"}))
async def report(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to report"),
        text: Option(str, "Tell us what you want to report")
):
    """Send a message to the moderators"""
    guild = guilds[ctx.guild_id]

    if guild.log.daily_report_count(ctx.author.id) > guild.config["reports_per_day"]:
        await ctx.respond("You've sent too many reports in the past 24 hours, please wait a bit", ephemeral=True,
                          delete_after=5)
        return

    guild.log.add_report(ctx.channel.id, name.id, ctx.author.id, text)
    await (await guild.fetch_mod_channel()).send(f"{ctx.author.mention} would like to report {name.mention} "
                                                 f"in {ctx.channel.mention} for the following:\n{text}")
    await ctx.respond("Report sent", ephemeral=True)


@bot.slash_command(guild_ids=config.guilds_with_features({"LOG"}))
@is_mod()
async def note(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to make a note for"),
        text: Option(str, "Note")
):
    """Make a note in a users' log."""
    guild = guilds[ctx.guild_id]

    guild.log.add_note(name.id, ctx.author.id, text)
    await (await guild.fetch_mod_channel()) \
        .send(f"User {name.mention} has had a note added by {ctx.author.mention}: {text}")
    await ctx.respond("Note added", ephemeral=True)


@bot.slash_command(guild_ids=config.guilds_with_features({"LOG"}))
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

    await (await guild.fetch_mod_channel()).send(
        f"User {name.mention} has been warned by {ctx.author.mention}: {text}\n"
        f"Their warning count is now at {warn_count}")
    await ctx.respond(message, ephemeral=True)


@bot.slash_command(guild_ids=config.guilds_with_features({"LOG"}))
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


@bot.slash_command(guild_ids=config.guilds_with_features({"LOG"}))
@is_mod()
async def purgelog(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to clear the log for")
):
    """Remove everything in the log for a user"""
    guild = guilds[ctx.guild_id]

    num_removed = guild.log.remove(predicate=lambda entry: entry["user"] == name.id)

    if num_removed > 0:
        await (await guild.fetch_mod_channel()).send(f"{ctx.author.mention} purged the log of {name.mention}.")
        await ctx.respond("Matching entries removed", ephemeral=True)
    else:
        await ctx.respond("No matching entries found", ephemeral=True)


@bot.slash_command(guild_ids=config.guilds_with_features({"LOG"}))
@is_mod()
async def log(
        ctx,
        name: Option(SlashCommandOptionType.user, "User to display the log for")
):
    """Display the log of a user, will print the log in the current channel."""
    guild = guilds[ctx.guild_id]
    types = None
    authors = False

    if ctx.channel.id == (await guild.fetch_mod_channel()).id:
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


@bot.slash_command(guild_ids=config.guilds_with_features({"SCRIMS"}))
async def scrim(
        ctx,
        time: Option(str, "Time when the scrim will start, format must be 14:00, 14.00 or 1400"),
        name: Option(str, "Give this scrim a name", required=False),
        size: Option(int, "Number of players for this scrim, the default is 8", required=False)
):
    """Start a scrim in this channel."""
    guild = guilds[ctx.guild_id]

    await ctx.defer(ephemeral=True)

    if guild.is_on_timeout(ctx.author):
        await ctx.respond("Sorry buddy, you are on a timeout!", ephemeral=True)
        return

    match = re.match(r"([0-9]{1,2})[:.]?([0-9]{2})", str(time))

    if not match:
        await ctx.respond("Invalid time, format must be 14:00, 14.00 or 1400!", ephemeral=True)
        return

    if str(ctx.channel.id) not in guild.scrim_channels.keys():
        await ctx.respond("This is not a channel for organising scrims!", ephemeral=True)
        return

    scrim_hour, scrim_minute = match.groups()

    if int(scrim_hour) > 23 or int(scrim_minute) > 59:
        await ctx.respond("Invalid time.", ephemeral=True)
        return

    guild_time = datetime.now(guild.timezone)
    scrim_time = guild_time.replace(hour=int(scrim_hour), minute=int(scrim_minute), second=0, microsecond=0)

    if scrim_time < guild_time:
        scrim_time += timedelta(days=1)

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

    message: discord.Message = await ctx.channel.send(scrim_obj.generate_header_message())

    scrimname = f" {scrim_obj.name}" if scrim_obj.name is not None else ""
    thread = await message.create_thread(name=f"{scrim_hour}.{scrim_minute}{scrimname}")
    content = await thread.send("Loading scrim ...")
    scrim_data["thread"] = thread.id
    scrim_data["message"] = content.id

    guild.create_scrim_manager(scrim_obj)

    await ctx.respond(f"Scrim created for {tag.time(scrim_time)} (your local time)")


@bot.slash_command(guild_ids=config.guilds_with_features({"SCRIMS"}))
@is_mod()
async def kick(
        ctx,
        player: Option(SlashCommandOptionType.user, "User you want to kick from this scrim."),
        reason: Option(str, "Specify the reason for kicking the user from the scrim.", required=False)
):
    """Kick a player out of a scrim"""
    guild: scrimbot.Guild = guilds[ctx.guild_id]
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


scrim_timeout = discord.SlashCommandGroup(
    name="scrim-timeout",
    description="Timeout commands",
    guild_ids=config.guilds_with_features({"SCRIMS"}),
    permissions=MOD_PERMISSIONS)


@scrim_timeout.command(name="list")
async def timeout_list(
        ctx,
        user: Option(SlashCommandOptionType.user, "Filter the list for a user", required=False)):
    """Get a list of users on scrim-timeout"""
    guild: scrimbot.Guild = guilds[ctx.guild_id]

    users = []
    if user is None:
        for member in ctx.guild.members:
            if guild.is_on_timeout(member):
                users.append((member, guild.get_user_timeout(member.id)))
    else:
        if guild.is_on_timeout(user):
            users.append((user, guild.get_user_timeout(user.id)))

    if not users:
        if user is None:
            await ctx.respond("No users are on timeout.", ephemeral=True)
        else:
            await ctx.respond(f"{user} is not on timeout.", ephemeral=True)
        return

    resp = []
    for user, delta in users:
        if delta is None:
            s = f"{user} is on timeout indefinitly."
        else:
            s = f"{user} is on timeout with remaining time: {delta}."
        resp.append(s)

    await ctx.respond("\n".join(resp), ephemeral=True)


@scrim_timeout.command(name="remove")
async def timeout_remove(
        ctx,
        user: Option(SlashCommandOptionType.user, "User to reset the timeout for."),
        reason: Option(str, "Specify a reason.", required=False)):
    """Remove a user's scrim-timeout."""
    guild = guilds[ctx.guild_id]
    if not guild.is_on_timeout(user):
        await ctx.respond(f"{user} is not on timeout.", ephemeral=True)
        return

    delta = guild.get_user_timeout(user.id)
    try:
        guild.remove_user_timeout(user.id, reason)
    except ValueError:
        # User is not in guild._timeouts, but role is removed.
        await ctx.respond("Timeout role was removed.")
        return

    await ctx.respond(f"{user} was removed from timeout with {delta} remaining.",
                      ephemeral=True)

    msg = f"Timeout was cancelled with {delta} remaining."
    msg += f" Reason: {reason}." if reason else ""
    guild.log.add_note(user.id, ctx.author.id, msg)

    msg = f"Timeout for {user} was cancelled by {ctx.author} " \
          f"with {delta} remaining."
    msg += f" Reason: {reason}." if reason else ""
    _log.info(msg)


@scrim_timeout.command(name="set")
async def timeout_set(
        ctx,
        user: Option(SlashCommandOptionType.user, description="User to send into timeout."),
        duration: Option(str,
                         "Format: '1d 5h 30m' for 1 day, 5 hours and 30 mins. 'd', 'h', 'm' may be combined freely."),
        reason: Option(str, "Reason for the timeout.", required=False)):
    """Send user into scrim-timeout for a specified duration."""
    guild: scrimbot.Guild = guilds[ctx.guild_id]

    if guild.is_on_timeout(user):
        delta = guild.get_user_timeout(user.id)
        s = f"User is already on timeout"
        s += f"for another {delta}." if delta else "."
        await ctx.respond(s, ephemeral=True)
        return

    d_match = re.search(r"(-?[\d]+) ?d", duration)
    h_match = re.search(r"(-?[\d]+) ?h", duration)
    m_match = re.search(r"(-?[\d]+) ?m", duration)
    d = 0 if d_match is None else d_match.groups()[0]
    h = 0 if h_match is None else h_match.groups()[0]
    m = 0 if m_match is None else m_match.groups()[0]
    duration = timedelta(days=int(d), hours=int(h), minutes=int(m))

    if duration <= timedelta(0):
        # negative duration or duration is 0
        await ctx.respond(f"Invalid duration: {duration}.\nDuration must be positive", ephemeral=True)
        return

    guild.add_user_timeout(user.id, duration, reason=reason)
    await ctx.respond(f"{user} was sent into timeout for {duration}.",
                      ephemeral=True)

    msg = f"User was sent into timeout for {duration}."
    msg += f" Reason: {reason}." if reason else ""
    guild.log.add_note(user.id, ctx.author.id, msg)

    msg = f"{user} was sent into timeout by {ctx.author} for {duration}."
    msg += f" Reason: {reason}." if reason else ""
    _log.info(msg)


bot.add_application_command(scrim_timeout)


@bot.slash_command(name="ping-scrim", guild_ids=config.guilds_with_features({"SCRIMS", "SCRIM_PING"}))
async def scrim_ping(
        ctx,
        text: Option(str, "Text to ping the scrim with")
):
    """Ping all players in the scrim"""
    guild: scrimbot.Guild = guilds[ctx.guild_id]
    scrim_manager = guild.get_scrim_manager(ctx.channel.id)

    if scrim_manager is None:
        await ctx.respond("Sorry, there is no (active) scrim in this channel.", ephemeral=True)
        return

    response, ephemeral = scrim_manager.ping(text, ctx.author.id)

    await ctx.respond(response, ephemeral=ephemeral)


@bot.slash_command(name="active-scrims", guild_ids=config.guilds_with_features({"SCRIMS"}))
async def active_scrims(ctx):
    """Get a list of active scrims that haven't started yet (10 max)"""
    guild = guilds[ctx.guild_id]

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


@bot.slash_command(guild_ids=config.guilds_with_features({"TIME"}))
async def time(ctx):
    """Show server time"""
    guild = guilds[ctx.guild_id]

    server_time = datetime.now(guild.timezone)

    await ctx.respond(f"**Server timezone**\n"
                      f"{guild.timezone.zone}\n"
                      f"**Server time**\n"
                      f"{server_time.strftime('%H:%M')}\n"
                      f"**Discord time tag**\n"
                      f"{tag.time(server_time)}", ephemeral=True)


@bot.slash_command(name="archive-scrim", guild_ids=config.guilds_with_features({"SCRIMS"}))
@is_mod()
async def archive_scrim(ctx):
    """Archive an open scrim thread"""
    guild = guilds[ctx.guild_id]

    if not isinstance(ctx.channel, discord.Thread):
        await ctx.respond("This isn't a thread", ephemeral=True)
        return

    if str(ctx.channel.parent_id) not in guild.scrim_channels.keys():
        await ctx.respond("This isn't a thread in a scrim channel", ephemeral=True)
        return

    guild.queue_task(ctx.channel.archive())
    await ctx.respond("Scrim thread will be archived in a short while", ephemeral=True)


@bot.slash_command(name="oculus-set", guild_ids=config.guilds_with_features({"OCULUS"}))
async def oculus_profile_set(
        ctx: discord.ApplicationContext,
        profile: Option(str, "Oculus profile link, get it from the phone app: menu > people > blue \"share\" button")
):
    """Give scrimbot your oculus profile link for easy friending. Requires oculus phone app."""
    await ctx.defer(ephemeral=True)
    response = await oculus_profiles.set_profile(ctx.author, profile)
    await ctx.respond(response, ephemeral=True)


@bot.slash_command(name="oculus-get", guild_ids=config.guilds_with_features({"OCULUS"}))
async def oculus_profile_get(
        ctx: discord.ApplicationContext,
        user: Option(SlashCommandOptionType.user, "User you want to see a the oculus profile for")
):
    """Get a link to the oculus profile of a discord user."""
    embed = await oculus_profiles.get_embed(user.id, user)
    if embed is None:
        await ctx.respond(f"No profile found for {user}", ephemeral=True)
        return

    await ctx.respond(f"Profile for {user}", embeds=[embed], ephemeral=False)


@bot.event
async def on_member_update(before, after):
    guild = guilds.get(after.guild.id, None)
    if guild is not None:
        guild.on_member_update(before, after)


bot.run(config.token)
