import asyncio
import math
from datetime import datetime, timedelta

import discord

import scrimbot


class Scrim:

    def __init__(self, guild: scrimbot.Guild, data: dict, sync, remove):
        self.guild = guild
        self.__sync = sync
        self.data = data
        self.__size = 8
        self.__remove = remove

        self.id = data["thread"]

        if "players" not in self.data:
            self.data["players"] = []

        if "reserve" not in self.data:
            self.data["reserve"] = []

        self.time = datetime.fromtimestamp(data["time"], self.guild.timezone)

    async def init(self):
        self.__view = scrimbot.ScrimView(self)

        self.__thread = await self.guild.bot.fetch_channel(self.id)
        self.__message = await self.__thread.fetch_message(self.data["message"])
        self.__guild = await self.guild.bot.fetch_guild(int(self.guild.id))
        self.__role = self.__guild.get_role(self.data["role"])
        self.__creator = await self.__guild.fetch_member(self.data["creator"])

        self.guild.bot.loop.create_task(self.__start_scrim())

        await self.update()

    async def update(self):
        if self.__thread.archived:
            self.__remove(self)
            return

        if self.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            self.__view = None

        elif (self.time < datetime.now(self.guild.timezone) or "started" in self.data) and self.__view.use == "before":
            if await self.num_reserves() > 0 and await self.num_players() > 0 and self.__get_next_reserve() is not None:
                self.__view = scrimbot.ScrimRunningView(self)
            else:
                self.__view = None

        name = await self.__generate_name()
        content = await self.__generate_message()

        await self.__message.edit(content=content, view=self.__view)

        if self.time < datetime.now(self.guild.timezone) - timedelta(hours=2):
            await self.__thread.edit(archived=True)

    async def num_players(self):
        return len(self.data["players"])

    async def num_reserves(self):
        return len(self.data["reserve"])

    async def __generate_message(self):
        message = f"{self.__role.mention}! Scrim at {scrimbot.tag.time(self.time)} " \
                  f"started by {self.__creator.mention}\n"
        if await self.num_players() > 0:
            players = await self.num_players()
            maxplayers = self.__size
            message += f"\n**Players ({players}/{maxplayers})**\n"
            for player in self.data["players"]:
                message += f"- {player['mention']}\n"

        if await self.num_reserves() > 0:
            reserves = await self.num_reserves()
            message += f"\n**Reserves ({reserves})**\n"
            for player in self.data["reserve"]:
                extra = ""
                if "auto" in player and "started" not in self.data:
                    extra = "(auto-join)"
                if "called" in player:
                    extra = "(called)"
                message += f"- {player['mention']} {extra}\n"

        return message

    async def __generate_name(self):
        players = await self.num_players()

        time = self.time.strftime("%H%M")

        return f"{time} {players}"

    async def join(self, user: discord.Member) -> str:
        if self.guild.is_on_timeout(user):
            return "Sorry buddy, you are on a timeout!"

        await self.__thread.add_user(user)
        if await self.num_players() < self.__size:
            if not any(u["id"] == user.id for u in self.data["players"]):
                self.data["players"].append(user_dict(user))
                self.__sync()
                self.__remove_reserve(user.id)
                await self.update()
                return "Added you to the scrim."
            else:
                return "Whoops, you are already in there!"
        else:
            await self.reserve(user)
            self.__set_auto_join(user)
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
            await self.__remove_player(user.id)
            await self.update()
            return "Put you on the reserve list."
        else:
            self.__set_auto_join(user, False)
            await self.update()
            return "You are already a reserve, turned off auto-join if it was on."

    def __set_auto_join(self, user: discord.Member, auto=True):
        for player in self.data["reserve"]:
            if player["id"] == user.id:
                if auto:
                    player["auto"] = True
                elif "auto" in player:
                    del player["auto"]
                self.__sync()
                break

    async def leave(self, user: discord.Member):
        await self.__remove_player(user.id)
        self.__remove_reserve(user.id)

        self.__sync()
        await self.update()

    async def call_reserve(self):
        callout = "No reserve available"
        ephemeral = True

        reserve = self.__get_next_reserve()
        if reserve is not None:
            reserve["called"] = True
            callout = f"{reserve['mention']} you are needed! Get online if you can!"
            ephemeral = False
            self.__sync()
        await self.update()
        return callout, ephemeral

    def __get_next_reserve(self):
        for r in self.data["reserve"]:
            if "called" not in r:
                return r
        return None

    async def __remove_player(self, player_id):
        self.__remove_from_playerlist("players", player_id)
        if await self.num_players() < self.__size:
            auto = None
            for r in self.data["reserve"]:
                if "auto" in r:
                    auto = r
                    break

            if auto is not None:
                self.data["reserve"].remove(auto)
                if "auto" in auto:
                    del auto["auto"]
                self.data["players"].append(auto)
                self.__sync()
                await self.update()

    def __remove_reserve(self, player_id):
        self.__remove_from_playerlist("reserve", player_id)

    def __remove_from_playerlist(self, playerlist, player_id):
        if playerlist not in self.data:
            return

        player = None

        for x in self.data[playerlist]:
            if x["id"] == player_id:
                player = x
                break

        if player:
            self.data[playerlist].remove(player)

    def contains_player(self, user: int) -> bool:
        for x in self.data["players"]:
            if x["id"] == user:
                return True

        for x in self.data["reserve"]:
            if x["id"] == user:
                return True

        return False

    async def __start_scrim(self):
        if "started" in self.data:
            return

        now = datetime.now(self.guild.timezone)
        if self.time > now:
            seconds = math.floor((self.time - now).total_seconds())
            await asyncio.sleep(seconds)

        self.data["started"] = True
        self.__sync()

        if not self.__thread.archived:
            await self.__thread.send(await self.__generate_start_message())

        await self.update()

        if await self.num_players() == 0:
            await self.__thread.edit(archived=True)

        now = datetime.now(self.guild.timezone)
        archive_time = self.time + timedelta(hours=2, minutes=5)
        if archive_time > now:
            seconds = math.floor((archive_time - now).total_seconds())
            await asyncio.sleep(seconds)

        await self.update()

    async def __generate_start_message(self):
        if await self.num_players() == 0:
            return "Sad moment, nobody signed up! Archiving the thread."

        players = ""
        numplayers = await self.num_players()
        reserves = ""
        numreserves = await self.num_reserves()

        for player in self.data["players"]:
            players += f"{player['mention']} "

        for player in self.data["reserve"]:
            reserves += f"{player['mention']} "

        if numplayers == self.__size:
            return f"Scrim starting, get online!\n" \
                   f"{players}"

        if numplayers + numreserves >= self.__size:
            return f"Scrim starting, get online!\n" \
                   f"{players}\n" \
                   f"Reserves, we need you!\n" \
                   f"{reserves}"

        message = f"Not enough players, feel free to get online and try to get it started anyway!\n" \
                  f"{players}\n"

        if numreserves > 0:
            message += f"Reserves, feel free to join in.\n" \
                       f"{reserves}"

        shortage = self.__size - numplayers + numreserves
        if shortage <= 2:
            message += f"\n{self.__role.mention}, you might be able to make this a full scrim.\n" \
                       f"We need at least {shortage} player(s)."

        return message


def user_dict(user: discord.Member) -> dict:
    return {"id": user.id, "name": user.display_name, "mention": user.mention}
