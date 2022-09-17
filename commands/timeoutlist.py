import logging
import re
from datetime import timedelta

import discord
from discord import Option, Permissions
from discord.ext.commands import Cog

import scrimbot

_log = logging.getLogger(__name__)


class TimeoutList(Cog):

    def __init__(self, guilds: dict[int, scrimbot.Guild]):
        self.guilds = guilds

    scrim_timeout = discord.SlashCommandGroup(
        name="scrim-timeout",
        description="Timeout commands",
        default_member_permissions=Permissions(administrator=True))

    @scrim_timeout.command(name="list")
    async def timeout_list(self, ctx,
                           user: Option(discord.Member, "Filter the list for a user", required=False)):
        """Get a list of users on scrim-timeout"""
        guild: scrimbot.Guild = self.guilds[ctx.guild_id]

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
    async def timeout_remove(self, ctx,
                             user: Option(discord.Member, "User to reset the timeout for."),
                             reason: Option(str, "Specify a reason.", required=False)):
        """Remove a user's scrim-timeout."""
        guild = self.guilds[ctx.guild_id]
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
    async def timeout_set(self, ctx,
                          user: Option(discord.Member, description="User to send into timeout."),
                          duration: Option(str,
                                           "Format: '1d 5h 30m' for 1 day, 5 hours and 30 mins. 'd', 'h', 'm' may be combined freely."),
                          reason: Option(str, "Reason for the timeout.", required=False)):
        """Send user into scrim-timeout for a specified duration."""
        guild: scrimbot.Guild = self.guilds[ctx.guild_id]

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
        guild.log.add_timeout(user.id, ctx.author.id, msg)

        msg = f"{user} was sent into timeout by {ctx.author} for {duration}."
        msg += f" Reason: {reason}." if reason else ""
        _log.info(msg)
