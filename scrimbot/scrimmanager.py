import asyncio
import math
from datetime import datetime, timedelta
from typing import Optional

import discord

import scrimbot
from scrimbot import DiscordProxy


class ScrimManager:

    def __init__(self, guild: scrimbot.Guild, scrim: scrimbot.Scrim, remove):
        self.guild = guild
        self.scrim = scrim
        self.__remove = remove
        self.broadcast = 0

        self.id = self.scrim.id
        self.url = ""

        self.__view: Optional[discord.ui.View] = None

        async def fetch_thread() -> discord.Thread:
            return await self.guild.bot.fetch_channel(self.id)

        self.__thread: DiscordProxy[discord.Thread] = DiscordProxy(fetcher=fetch_thread,
                                                                   on_fetch=self.on_thread_fetched)
        self.__start_message: DiscordProxy[discord.Message] = DiscordProxy()
        self.__content_message: DiscordProxy[discord.Message] = DiscordProxy(on_fetch=self.on_content_message_fetched)

    async def init(self):
        self.__view = scrimbot.ScrimView(self)
        await self.__thread.fetch()

        self.guild.queue_task(self.__start_scrim())
        self.guild.queue_task(self.__update())

    async def on_thread_fetched(self, thread: discord.Thread):
        scrim_channel: discord.TextChannel = thread.parent
        scrim_channel_settings = self.guild.scrim_channel_config(scrim_channel.id)
        self.scrim.settings = scrim_channel_settings

        self.broadcast = scrim_channel_settings["broadcast_channel"] \
            if "broadcast_channel" in scrim_channel_settings else 0

        await self.__start_message.fetch(lambda: scrim_channel.fetch_message(self.id))
        await self.__content_message.fetch(lambda: thread.fetch_message(self.scrim.data["message"]))

    async def on_content_message_fetched(self, message: discord.Message):
        self.url = message.jump_url

    async def __update(self):
        if await self.__thread.fetch() and self.__thread.content.archived:
            await self.__end()
            return

        if self.scrim.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            self.__view = None

        elif (self.scrim.time < datetime.now(self.guild.timezone) or self.scrim.started) and \
                hasattr(self.__view, "use") and self.__view.use == "before":
            if self.scrim.num_reserves > 0 and self.scrim.num_players > 0 and \
                    self.scrim.get_next_reserve() is not None:
                self.__view = scrimbot.ScrimRunningView(self)
            else:
                self.__view = None

        await self.__content_message.wait(
            lambda m: m.edit(content="", embeds=[self.create_rich_embed()], view=self.__view))
        await self.__start_message.wait(
            lambda m: m.edit(content=self.scrim.generate_header_message()))

        if self.scrim.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            await self.__end()

        if self.scrim.started and self.scrim.num_players == 0:
            await self.__end()

        self.guild.queue_task(self.guild.update_broadcast())

    async def __end(self):
        await self.__thread.wait(lambda t: t.edit(archived=True))
        self.__remove(self)
        self.guild.queue_task(self.guild.update_broadcast())

    def create_rich_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"Mixed scrim",
                              description=self.scrim.scrim_time(separator='\n'),
                              type="rich",
                              colour=discord.Colour.green(),
                              url=self.url)
        player_list = self.scrim.generate_player_list() if self.scrim.num_players > 0 else "no signups yet"

        embed.add_field(name=f"Players ({self.scrim.num_players}/{self.scrim.size})",
                        value=player_list,
                        inline=True)

        reserve_list = self.scrim.generate_reserve_list() if self.scrim.num_reserves > 0 else "no reserves"

        embed.add_field(name=f"Reserves ({self.scrim.num_reserves})",
                        value=reserve_list,
                        inline=True)

        author = self.scrim.author
        embed.set_author(name=author["name"], icon_url=author["avatar"])
        return embed

    def create_link_embed(self):
        full = " **FULL**" if self.scrim.full else ""
        embed = discord.Embed(title=f"Mixed scrim {full}",
                              description=self.scrim.scrim_time(separator='\n'),
                              type="rich",
                              colour=discord.Colour.green(),
                              url=self.url)
        author = self.scrim.author
        embed.set_author(name=author["name"], icon_url=author["avatar"])
        return embed

    async def join(self, user: discord.Member) -> str:
        if self.guild.is_on_timeout(user):
            return "Sorry buddy, you are on a timeout!"

        await self.__thread.wait(lambda t: t.add_user(user))
        if not self.scrim.full:
            if not self.scrim.contains_player(user.id):
                self.scrim.add_player(user_dict(user))
                self.guild.queue_task(self.__update())
                return "Added you to the scrim."
            else:
                return "Whoops, you are already in there!"
        else:
            await self.reserve(user)
            self.scrim.set_auto_join(user.id)
            self.guild.queue_task(self.__update())
            return "It's full, sorry! I put you on the reserve on auto-join, if a spot opens up the first reserve on " \
                   "auto-join will get it. If you don't want auto-join just press the **reserve** button."

    async def reserve(self, user: discord.Member) -> str:
        if self.guild.is_on_timeout(user):
            return "Sorry buddy, you are on a timeout!"

        await self.__thread.wait(lambda t: t.add_user(user))
        if not self.scrim.contains_reserve(user.id):
            self.scrim.add_reserve(user_dict(user))
            self.guild.queue_task(self.__update())
            if self.scrim.full:
                return "Put you on the reserve list, if you would like to join as soon as a spot opens up click " \
                       "**join** to turn on auto-join. If a spot opens up the first reserve on auto-join will " \
                       "get it. If you don't want auto-join just press the **reserve** button again."
            return "Put you on the reserve list."
        else:
            self.scrim.set_auto_join(user.id, False)
            self.guild.queue_task(self.__update())
            return "You are already a reserve, turned off auto-join if it was on."

    async def leave(self, user: discord.Member):
        self.scrim.remove_player(user.id)
        self.scrim.remove_reserve(user.id)
        self.guild.queue_task(self.__update())

    async def call_reserve(self):
        callout = "No reserve available"
        ephemeral = True

        reserve = self.scrim.call_next_reserve()
        if reserve is not None:
            callout = f"{reserve['mention']} you are needed! Get online if you can!"
            ephemeral = False
        self.guild.queue_task(self.__update())
        return callout, ephemeral

    def contains_player(self, user: int) -> bool:
        return self.scrim.contains_user(user)

    async def __start_scrim(self):
        now = datetime.now(self.guild.timezone)
        if self.scrim.time > now:
            seconds = math.floor((self.scrim.time - now).total_seconds())
            await asyncio.sleep(seconds)

        if not self.scrim.started:
            thread_msg, channel_msg = self.scrim.generate_start_messages()
            await self.__thread.wait(lambda t: t.send(thread_msg))
            if channel_msg is not None:
                await self.__start_message.wait(lambda s: s.reply(channel_msg))
            self.scrim.started = True

        self.guild.queue_task(self.__update())

        now = datetime.now(self.guild.timezone)
        archive_time = self.scrim.time + timedelta(hours=2, minutes=5)
        if archive_time > now:
            seconds = math.floor((archive_time - now).total_seconds())
            await asyncio.sleep(seconds)

        self.guild.queue_task(self.__update())


def user_dict(user: discord.Member) -> dict:
    return {"id": user.id, "name": user.display_name, "mention": user.mention}
