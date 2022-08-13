import discord
from discord import Option, slash_command
from discord.ext.commands import Cog

import scrimbot
from scrimbot import config


class Moderation(Cog):

    def __init__(self, guilds):
        self.guilds = guilds

    @slash_command(guild_ids=config.guilds_with_features({"LOG", "REPORT"}))
    async def report(self, ctx,
                     name: Option(discord.Member, "User to report"),
                     text: Option(str, "Tell us what you want to report")
                     ):
        """Send a message to the moderators"""
        guild = self.guilds[ctx.guild_id]

        if guild.log.daily_report_count(ctx.author.id) > guild.config["reports_per_day"]:
            await ctx.respond("You've sent too many reports in the past 24 hours, please wait a bit", ephemeral=True,
                              delete_after=5)
            return

        guild.log.add_report(ctx.channel.id, name.id, ctx.author.id, text)
        await (await guild.fetch_mod_channel()).send(f"{ctx.author.mention} would like to report {name.mention} "
                                                     f"in {ctx.channel.mention} for the following:\n{text}")
        await ctx.respond("Report sent", ephemeral=True)

    @slash_command(guild_ids=config.guilds_with_features({"LOG"}))
    @discord.default_permissions(administrator=True)
    async def note(self, ctx,
                   name: Option(discord.Member, "User to make a note for"),
                   text: Option(str, "Note")
                   ):
        """Make a note in a users' log."""
        guild = self.guilds[ctx.guild_id]

        guild.log.add_note(name.id, ctx.author.id, text)
        await (await guild.fetch_mod_channel()) \
            .send(f"User {name.mention} has had a note added by {ctx.author.mention}: {text}")
        await ctx.respond("Note added", ephemeral=True)

    @slash_command(guild_ids=config.guilds_with_features({"LOG"}))
    @discord.default_permissions(administrator=True)
    async def warn(self, ctx,
                   name: Option(discord.Member, "User to make a note for"),
                   text: Option(str, "Warning")
                   ):
        """Warn a user. A DM will be sent to the user as well."""
        guild = self.guilds[ctx.guild_id]

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

    @slash_command(guild_ids=config.guilds_with_features({"LOG"}))
    @discord.default_permissions(administrator=True)
    async def rmlog(self, ctx,
                    id: Option(str, "ID of the entry to remove, it's the gibberish in square brackets [] in the log")
                    ):
        """Remove a single log entry from a user"""
        guild = self.guilds[ctx.guild_id]

        num_removed = guild.log.remove(predicate=lambda entry: entry["id"] == id)

        if num_removed > 0:
            await ctx.respond("Entry removed", ephemeral=True)
        else:
            await ctx.respond("No matching entries found", ephemeral=True)

    @slash_command(guild_ids=config.guilds_with_features({"LOG"}))
    @discord.default_permissions(administrator=True)
    async def purgelog(self, ctx,
                       name: Option(discord.Member, "User to clear the log for")
                       ):
        """Remove everything in the log for a user"""
        guild = self.guilds[ctx.guild_id]

        num_removed = guild.log.remove(predicate=lambda entry: entry["user"] == name.id)

        if num_removed > 0:
            await (await guild.fetch_mod_channel()).send(f"{ctx.author.mention} purged the log of {name.mention}.")
            await ctx.respond("Matching entries removed", ephemeral=True)
        else:
            await ctx.respond("No matching entries found", ephemeral=True)

    @slash_command(guild_ids=config.guilds_with_features({"LOG"}))
    @discord.default_permissions(administrator=True)
    async def log(self, ctx,
                  name: Option(discord.Member, "User to display the log for")
                  ):
        """Display the log of a user, will print the log in the current channel."""
        guild = self.guilds[ctx.guild_id]
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

        entries.append(
            f"**Warnings / last 7 days:** {guild.log.warning_count(name.id)}/{guild.log.weekly_warning_count(name.id)}")
        entries.append(f"**Number of played scrims:** {guild.log.scrim_count(name.id)}")

        for entry in entries:
            if len(output + entry) > 1800:
                await ctx.respond(output)
                output = entry
            else:
                output += "\n" + entry
        await ctx.respond(output)

    @slash_command(guild_ids=config.guilds_with_features({"LOG"}))
    @discord.default_permissions(administrator=True)
    async def warn_list(self, ctx,
                        sorting: Option(str, "Sorting to apply", choices=["recent", "all"])
                        ):
        """Display the list of all users that have warnings."""
        guild = self.guilds[ctx.guild_id]
        entries = guild.log.print_warning_top(recent=(sorting == "recent"))

        output = f"**Warning top**\n *(all time/recent)*"
        for entry in entries:
            if len(output + entry) > 1800:
                await ctx.respond(output)
                output = entry
            else:
                output += "\n" + entry
        await ctx.respond(output)

    @slash_command(guild_ids=config.guilds_with_features({"LOG"}))
    async def scrim_top(self, ctx):
        """Display the list of all users that played scrims"""
        guild = self.guilds[ctx.guild_id]
        entries = guild.log.print_scrim_top()

        output = f"**Scrim top**"
        for entry in entries:
            if len(output + entry) > 1800:
                await ctx.respond(output)
                output = entry
            else:
                output += "\n" + entry
        await ctx.respond(output)
