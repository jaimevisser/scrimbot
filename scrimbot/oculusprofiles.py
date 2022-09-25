import html
import logging
import re
from typing import Optional

import aiohttp
import discord

import scrimbot
from scrimbot import tag

_log = logging.getLogger(__name__)


class OculusProfiles:

    def __init__(self, bot: discord.Bot, guilds: scrimbot.Guilds):
        self.guilds = guilds
        self.__bot = bot
        self.__profiles: scrimbot.Store[dict] = scrimbot.Store[dict]("data/oculus_profiles.json", {})
        self.__session = aiohttp.ClientSession()

    async def refresh_profile(self, user: discord.Member):
        data: Optional[dict] = self.__profiles.data.get(str(user.id), None)

        if data is None:
            return "User currently has no profile!"

        return await self.set_profile(user, data['profile_url'])

    async def set_profile(self, user: discord.Member, profile_link: str):

        profile_link = re.sub(r'^.*?https://', r'https://', profile_link)

        help_text = "\n\nAre you sure you gave an oculus share link as input? You need to be logged into your " \
                    "Oculus/Meta account on the phone app and go to *menu* > *people*, press the blue share button " \
                    "and copy. Use this command again, pasting that text (you can leave the text in front of the " \
                    "profile URL, I'm smart enough to remove it myself)."

        try:
            async with self.__session.get(profile_link) as resp:
                content = await resp.text()

            match = re.search(r'<img class=".*? img" alt="(.*?)" src="([^"]*?)" height=".*?" width=".*?" />',
                              content)
        except aiohttp.ClientError as err:
            _log.error(f"Could not extract data from {profile_link}")
            _log.exception(err)
            return f"Could not access oculus profile.{help_text}"

        if not match:
            _log.error(f"Could not extract data from {profile_link}")
            return f"Could not extract data from oculus profile.{help_text}"

        oculus_name, oculus_avatar = match.groups()
        oculus_avatar = html.unescape(oculus_avatar)

        async with self.__session.get(f"https://api.ignitevr.gg/ignitevr/stats/player/{oculus_name}") as resp:
            content = await resp.json()

        aka = content.get_filename('player', {}).get_filename('previous_names', [])

        self.__profiles.data[str(user.id)] = {
            "name": oculus_name,
            "avatar": oculus_avatar,
            "previous_names": aka,
            "profile_url": profile_link
        }
        self.__sync()

        return "Profile set!"

    def __sync(self):
        async def inner():
            self.__profiles.sync()

        self.__bot.loop.create_task(inner())

    def get_profile(self, user: discord.Member) -> dict:
        return self.__profiles.data.get(str(user.id), {})

    async def get_embed(self, user: int, long=True, guild=None) -> Optional[discord.Embed]:
        data: Optional[dict] = self.__profiles.data.get(str(user), None)

        if data is None:
            return

        description = f"Discord: {tag.user(user)}"
        if long:
            description += f"\n[Ignite stats](https://ignitevr.gg/stats/player/{data['name']})"

        embed = discord.Embed(title=f"Oculus profile of {data['name']}",
                              description=description,
                              url=data['profile_url'],
                              colour=discord.Colour.blue()
                              )

        if long and len(data['previous_names']) > 0:
            embed.add_field(name="Previous names", value="\n".join(data['previous_names']), inline=True)

        if long and guild is not None:
            guild = await self.guilds.get(guild)
            scrim_count = guild.log.scrim_count(user)
            embed.add_field(name="Scrims played", value=scrim_count, inline=True)

        embed.set_thumbnail(url=data['avatar'])

        return embed
