import discord
from discord import Option, slash_command
from discord.ext.commands import Cog

import scrimbot
from scrimbot import config

OCU_SET_HELP = "Oculus profile link, get it from the phone app: menu > people > blue \"share\" button"


class Oculus(Cog):

    def __init__(self, guilds: dict[int, scrimbot.Guild], profiles: scrimbot.OculusProfiles):
        self.guilds = guilds
        self.oculus_profiles = profiles

    @slash_command(name="oculus-set", guild_ids=config.guilds_with_features({"OCULUS"}))
    async def oculus_profile_set(self, ctx: discord.ApplicationContext,
                                 profile: Option(str, OCU_SET_HELP)
                                 ):
        """Give scrimbot your oculus profile link for easy friending. Requires oculus phone app."""
        await ctx.defer(ephemeral=True)
        response = await self.oculus_profiles.set_profile(ctx.author, profile)
        await ctx.respond(response, ephemeral=True)

    @slash_command(name="oculus-get", guild_ids=config.guilds_with_features({"OCULUS"}))
    async def oculus_profile_get(self, ctx: discord.ApplicationContext,
                                 user: Option(discord.Member, "User you want to see a the oculus profile for")
                                 ):
        """Get a link to the oculus profile of a discord user."""
        embed = await self.oculus_profiles.get_embed(user.id, user)
        if embed is None:
            await ctx.respond(f"No profile found for {user}", ephemeral=True)
            return

        await ctx.respond(f"Profile for {user}", embeds=[embed], ephemeral=False)
