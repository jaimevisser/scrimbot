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

    def __init__(self, bot: discord.Bot):
        self.__bot = bot
        self.__profiles: scrimbot.Store[dict] = scrimbot.Store[dict]("data/oculus_profiles.json", {})
        self.__session = aiohttp.ClientSession()

    async def set_profile(self, user: discord.Member, profile_link: str):

        profile_link = re.sub(r'^.*?https://', r'https://', profile_link)

        try:
            async with self.__session.get(profile_link) as resp:
                content = await resp.text()

            match = re.search(r'<img class="_96ij img" alt="(.*?)" src="(.*?)" height="256" width="256" />',
                              content)
        except aiohttp.ClientError as err:
            _log.error(f"Could not extract data from {profile_link}")
            _log.exception(err)
            return "Could not access oculus profile"

        if not match:
            _log.error(f"Could not extract data from {profile_link}")
            return "Could not extract data from oculus profile"

        oculus_name, oculus_avatar = match.groups()
        oculus_avatar = html.unescape(oculus_avatar)

        async with self.__session.get(f"https://ignitevr.gg/stats/player/{oculus_name}") as resp:
            content = await resp.text()

        aka = []

        for match in re.finditer(r'<h3 style="line-height: inherit;margin: 1em;">aka (.*?)</h3>', content):
            aka.append(match.groups()[0])

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

    async def get_embed(self, user: int, long=True) -> Optional[discord.Embed]:

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

        embed.set_thumbnail(url=data['avatar'])

        return embed
