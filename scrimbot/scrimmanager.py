import asyncio
import math
from datetime import datetime, timedelta

import discord
from discord import Color

import scrimbot
from scrimbot import tag
from scrimbot.scrim import Scrim


class ScrimManager:

    def __init__(self, guild: scrimbot.Guild, data: dict, sync, remove):
        self.guild = guild
        self.__sync = sync
        self.scrim = Scrim(data, self.guild.timezone, sync)
        self.__remove = remove

        self.broadcast = 0

        self.id = self.scrim.id
        self.url = ""

    async def init(self):
        self.__view = scrimbot.ScrimView(self)

        self.__thread = await self.guild.bot.fetch_channel(self.id)

        scrim_channel = self.__thread.parent
        scrim_channel_settings = self.guild.scrim_channel_config(scrim_channel.id)

        self.broadcast = scrim_channel_settings["broadcast_channel"] \
            if "broadcast_channel" in scrim_channel_settings else 0

        self.__startmessage = await scrim_channel.fetch_message(self.id)
        self.__contentmessage = await self.__thread.fetch_message(self.scrim.data["message"])

        self.url = f"https://discordapp.com/channels/{self.guild.id}/{self.id}/{self.__contentmessage.id}"

        self.guild.queue_task(self.__start_scrim())
        self.guild.queue_task(self.update())

    def generate_broadcast_listing(self) -> str:
        return self.scrim.generate_broadcast_listing() + "\n" + self.url

    async def update(self):
        if self.__thread.archived:
            self.__remove(self)
            self.guild.queue_task(self.guild.update_broadcast())
            return

        if self.scrim.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            self.__view = None

        elif (self.scrim.time < datetime.now(self.guild.timezone) or "started" in self.scrim.data) and \
                self.__view.use == "before":
            if self.scrim.num_reserves() > 0 and self.scrim.num_players() > 0 and \
                    self.scrim.get_next_reserve() is not None:
                self.__view = scrimbot.ScrimRunningView(self)
            else:
                self.__view = None

        await self.__contentmessage.edit(content="", embeds=[self.create_rich_embed()], view=self.__view)
        await self.__startmessage.edit(content=self.scrim.generate_header_message())

        if self.scrim.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            await self.__thread.edit(archived=True)

        self.guild.queue_task(self.guild.update_broadcast())

    def create_rich_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"Mixed scrim at {tag.time(self.scrim.time)} (local time)",
                              type="rich",
                              colour=discord.Colour.green(),
                              timestamp=self.scrim.time,
                              url=self.url)
        player_list = self.scrim.generate_player_list() if self.scrim.num_players() > 0 else "no signups yet"

        embed.add_field(name=f"Players ({self.scrim.num_players()}/{self.scrim.size})",
                        value=player_list,
                        inline=True)

        reserve_list = self.scrim.generate_reserve_list() if self.scrim.num_reserves() > 0 else "no reserves"

        embed.add_field(name=f"Reserves ({self.scrim.num_reserves()})",
                        value=reserve_list,
                        inline=True)

        author = self.scrim.author
        embed.set_author(name=author["name"], icon_url=author["avatar"])
        return embed

    def create_link_embed(self):
        full = " **FULL**" if self.scrim.full else ""
        embed = discord.Embed(title=f"Mixed scrim at {tag.time(self.scrim.time)} (local time){full}",
                              type="rich",
                              colour=discord.Colour.green(),
                              timestamp=self.scrim.time,
                              url=self.url)
        author = self.scrim.author
        embed.set_author(name=author["name"], icon_url=author["avatar"])
        return embed

    async def join(self, user: discord.Member) -> str:
        if self.guild.is_on_timeout(user):
            return "Sorry buddy, you are on a timeout!"

        await self.__thread.add_user(user)
        if not self.scrim.full:
            if not self.scrim.contains_player(user.id):
                self.scrim.add_player(user_dict(user))
                await self.update()
                return "Added you to the scrim."
            else:
                return "Whoops, you are already in there!"
        else:
            await self.reserve(user)
            self.scrim.set_auto_join(user.id)
            await self.update()
            return "It's full, sorry! I put you on the reserve on auto-join, if a spot opens up the first reserve on " \
                   "auto-join will get it. If you don't want auto-join just press the reserve button."

    async def reserve(self, user: discord.Member) -> str:
        if self.guild.is_on_timeout(user):
            return "Sorry buddy, you are on a timeout!"

        await self.__thread.add_user(user)
        if not self.scrim.contains_reserve(user.id):
            self.scrim.add_reserve(user_dict(user))
            await self.update()
            return "Put you on the reserve list."
        else:
            self.scrim.set_auto_join(user.id, False)
            await self.update()
            return "You are already a reserve, turned off auto-join if it was on."

    async def leave(self, user: discord.Member):
        self.scrim.remove_player(user.id)
        self.scrim.remove_reserve(user.id)
        self.__sync()
        await self.update()

    async def call_reserve(self):
        callout = "No reserve available"
        ephemeral = True

        reserve = self.scrim.get_next_reserve()
        if reserve is not None:
            reserve["called"] = True
            callout = f"{reserve['mention']} you are needed! Get online if you can!"
            ephemeral = False
            self.__sync()
        await self.update()
        return callout, ephemeral

    def contains_player(self, user: int) -> bool:
        return self.scrim.contains_user(user)

    async def __start_scrim(self):
        if "started" in self.scrim.data:
            return

        now = datetime.now(self.guild.timezone)
        if self.scrim.time > now:
            seconds = math.floor((self.scrim.time - now).total_seconds())
            await asyncio.sleep(seconds)

        self.scrim.data["started"] = True
        self.__sync()

        if not self.__thread.archived:
            await self.__thread.send(self.scrim.generate_start_message())

        await self.update()

        if self.scrim.num_players() == 0:
            await self.__thread.edit(archived=True)

        now = datetime.now(self.guild.timezone)
        archive_time = self.scrim.time + timedelta(hours=2, minutes=5)
        if archive_time > now:
            seconds = math.floor((archive_time - now).total_seconds())
            await asyncio.sleep(seconds)

        await self.update()


def user_dict(user: discord.Member) -> dict:
    return {"id": user.id, "name": user.display_name, "mention": user.mention}
