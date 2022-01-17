import asyncio
import math
from datetime import datetime, timedelta

import discord

import scrimbot
from scrimbot.scrim import Scrim


class ScrimManager:

    def __init__(self, guild: scrimbot.Guild, data: dict, sync, remove):
        self.guild = guild
        self.__sync = sync
        self.data = data
        self.scrim_data = Scrim(data, self.guild.timezone, sync)
        self.__remove = remove

        self.id = self.scrim_data.id

    async def init(self):
        self.__view = scrimbot.ScrimView(self)

        self.__thread = await self.guild.bot.fetch_channel(self.id)
        self.__startmessage = await self.__thread.parent.fetch_message(self.id)
        self.__contentmessage = await self.__thread.fetch_message(self.data["message"])

        self.guild.bot.loop.create_task(self.__start_scrim())

        await self.update()

    async def update(self):
        if self.__thread.archived:
            self.__remove(self)
            return

        if self.scrim_data.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            self.__view = None

        elif (self.scrim_data.time < datetime.now(self.guild.timezone) or "started" in self.data) and \
                self.__view.use == "before":
            if self.scrim_data.num_reserves() > 0 and self.scrim_data.num_players() > 0 and \
                    self.scrim_data.get_next_reserve() is not None:
                self.__view = scrimbot.ScrimRunningView(self)
            else:
                self.__view = None

        name = self.scrim_data.generate_name()
        content = self.scrim_data.generate_message()

        await self.__contentmessage.edit(content=content, view=self.__view)

        if self.scrim_data.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            await self.__thread.edit(archived=True)

    async def join(self, user: discord.Member) -> str:
        if self.guild.is_on_timeout(user):
            return "Sorry buddy, you are on a timeout!"

        await self.__thread.add_user(user)
        if self.scrim_data.num_players() < self.scrim_data.size:
            if not any(u["id"] == user.id for u in self.data["players"]):
                self.data["players"].append(user_dict(user))
                self.__sync()
                self.scrim_data.remove_reserve(user.id)
                await self.update()
                return "Added you to the scrim."
            else:
                return "Whoops, you are already in there!"
        else:
            await self.reserve(user)
            self.scrim_data.set_auto_join(user.id)
            await self.update()
            return "It's full, sorry! I put you on the reserve on auto-join, if a spot opens up the first reserve on " \
                   "auto-join will get it. If you don't want auto-join just press the reserve button."

    async def reserve(self, user: discord.Member) -> str:
        if self.guild.is_on_timeout(user):
            return "Sorry buddy, you are on a timeout!"

        await self.__thread.add_user(user)
        if not any(u["id"] == user.id for u in self.data["reserve"]):
            self.data["reserve"].append(user_dict(user))
            self.__sync()
            self.scrim_data.remove_player(user.id)
            await self.update()
            return "Put you on the reserve list."
        else:
            self.scrim_data.set_auto_join(user.id, False)
            await self.update()
            return "You are already a reserve, turned off auto-join if it was on."

    async def leave(self, user: discord.Member):
        self.scrim_data.remove_player(user.id)
        self.scrim_data.remove_reserve(user.id)
        self.__sync()
        await self.update()

    async def call_reserve(self):
        callout = "No reserve available"
        ephemeral = True

        reserve = self.scrim_data.get_next_reserve()
        if reserve is not None:
            reserve["called"] = True
            callout = f"{reserve['mention']} you are needed! Get online if you can!"
            ephemeral = False
            self.__sync()
        await self.update()
        return callout, ephemeral

    def contains_player(self, user: int) -> bool:
        return self.scrim_data.contains_player(user)

    async def __start_scrim(self):
        if "started" in self.data:
            return

        now = datetime.now(self.guild.timezone)
        if self.scrim_data.time > now:
            seconds = math.floor((self.scrim_data.time - now).total_seconds())
            await asyncio.sleep(seconds)

        self.data["started"] = True
        self.__sync()

        if not self.__thread.archived:
            await self.__thread.send(self.scrim_data.generate_start_message())

        await self.update()

        if self.scrim_data.num_players() == 0:
            await self.__thread.edit(archived=True)

        now = datetime.now(self.guild.timezone)
        archive_time = self.scrim_data.time + timedelta(hours=2, minutes=5)
        if archive_time > now:
            seconds = math.floor((archive_time - now).total_seconds())
            await asyncio.sleep(seconds)

        await self.update()


def user_dict(user: discord.Member) -> dict:
    return {"id": user.id, "name": user.display_name, "mention": user.mention}


