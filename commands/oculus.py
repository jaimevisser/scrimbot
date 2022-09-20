import discord
from discord import Option, slash_command
from discord.ext.commands import Cog

import scrimbot
from scrimbot import Guilds

OCU_SET_HELP = "Oculus profile link, get it from the phone app: menu > people > blue \"share\" button"


class Oculus(Cog):

    def __init__(self, guilds: Guilds, profiles: scrimbot.OculusProfiles):
        self.guilds = guilds
        self.oculus_profiles = profiles

    @slash_command(name="oculus-set")
    async def oculus_profile_set(self, ctx: discord.ApplicationContext,
                                 profile: Option(str, OCU_SET_HELP)
                                 ):
        """Give scrimbot your oculus profile link for easy friending. Requires oculus phone app."""
        await ctx.defer(ephemeral=True)
        response = await self.oculus_profiles.set_profile(ctx.author, profile)
        await ctx.respond(response, ephemeral=True)

    @slash_command(name="oculus-refresh")
    @discord.default_permissions(administrator=True)
    async def oculus_profile_refresh(self, ctx: discord.ApplicationContext,
                                     user: Option(discord.Member, "User you want to refresh the oculus profile for")
                                     ):
        """Fetch new data for an existing profile"""
        await ctx.defer(ephemeral=True)
        response = await self.oculus_profiles.refresh_profile(user)
        await ctx.respond(response, ephemeral=True)

    @slash_command(name="oculus-get")
    async def oculus_profile_get(self, ctx: discord.ApplicationContext,
                                 user: Option(discord.Member, "User you want to see a the oculus profile for")
                                 ):
        """Get a link to the oculus profile of a discord user."""
        embed = await self.oculus_profiles.get_embed(user.id, True, ctx.guild_id)
        if embed is None:
            await ctx.respond(f"No profile found for {user}", ephemeral=True)
            return

        await ctx.respond(f"Profile for {user}", embeds=[embed], ephemeral=False)
