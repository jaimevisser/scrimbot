import asyncio
import math
from datetime import datetime, timedelta

import pytz
from discord import Bot, Member

import discutils
from mixedview import MixedView, MixedRunningView

tzuk = pytz.timezone("Europe/London")


class Mixed:

    def __init__(self, bot: Bot, guild, data: dict, sync, remove):
        self.guild = str(guild)
        self.__sync = sync
        self.data = data
        self.__bot = bot
        self.__size = 8
        self.__remove = remove

        self.id = data["thread"]

        if "players" not in self.data:
            self.data["players"] = []

        if "reserve" not in self.data:
            self.data["reserve"] = []

        self.time = datetime.fromtimestamp(data["utc"], tzuk)

        self.__view = MixedView(self)

    async def __init(self):
        self.__thread = await self.__bot.fetch_channel(self.id)
        self.__message = await self.__thread.fetch_message(self.data["message"])

        self.__bot.loop.create_task(self.__start_mixed())

        await self.update()

    async def update(self):
        if self.__thread.archived:
            self.__remove(self)
            return

        if self.time < datetime.now(tzuk) - timedelta(hours=2):
            self.__view = None

        elif (self.time < datetime.now(tzuk) or "started" in self.data) and self.__view.use == "before":
            if await self.num_reserves() > 0 and await self.num_players() > 0 and self.__get_next_reserve() is not None:
                self.__view = MixedRunningView(self)
            else:
                self.__view = None

        name = await self.__generate_name()
        content = await self.__generate_message()

        print(name)
        print(content)

        await self.__message.edit(content=content, view=self.__view)

        if self.time < datetime.now(tzuk) - timedelta(hours=2):
            await self.__thread.edit(archived=True)

        print("done")

    async def num_players(self):
        return len(self.data["players"])

    async def num_reserves(self):
        return len(self.data["reserve"])

    async def __generate_message(self):
        message = f"Mixed scrim at {discutils.timestamp(self.time)}\n"
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
                called = ""
                if "called" in player:
                    called = "(called)"
                message += f"- {player['mention']} {called}\n"

        return message

    async def __generate_name(self):
        players = await self.num_players()

        time = self.time.strftime("%H%M")

        return f"{time} {players}"

    async def join(self, user: Member):
        self.__remove_reserve(user.id)

        if await self.num_players() < self.__size:
            await self.__thread.add_user(user)

            if not any(u["id"] == user.id for u in self.data["players"]):
                self.data["players"].append(discutils.user_dict(user))
                self.__sync()
                await self.update()

    async def reserve(self, user: Member):
        self.__remove_player(user.id)

        await self.__thread.add_user(user)
        if not any(u["id"] == user.id for u in self.data["reserve"]):
            self.data["reserve"].append(discutils.user_dict(user))
            self.__sync()
            await self.update()

    async def leave(self, user: Member):
        self.__remove_player(user.id)
        self.__remove_reserve(user.id)

        self.__sync()
        await self.update()

    async def call_reserve(self):
        callout = "No reserve available"

        reserve = self.__get_next_reserve()
        if reserve is not None:
            reserve["called"] = True
            callout = f"{reserve['mention']} you are needed! Get online if you can!"
            self.__sync()
        await self.update()
        return callout

    def __get_next_reserve(self):
        for r in self.data["reserve"]:
            if "called" not in r:
                return r
        return None

    def __remove_player(self, player_id):
        self.__remove_from_playerlist("players", player_id)

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

    async def __start_mixed(self):
        if "started" in self.data:
            return

        if self.time > datetime.now(tzuk):
            seconds = math.floor((self.time - datetime.now(tzuk)).total_seconds())
            await asyncio.sleep(seconds)

        self.data["started"] = True
        self.__sync()

        if not self.__thread.archived:
            await self.__thread.send(await self.__generate_start_message())

        await self.update()

        if await self.num_players() == 0:
            await self.__thread.edit(archived=True)

        archivetime = self.time + timedelta(hours=2, minutes=5)
        if archivetime > datetime.now(tzuk):
            seconds = math.floor((archivetime - datetime.now(tzuk)).total_seconds())
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
            return f"Mixed starting, get online!\n" \
                   f"{players}"

        if numplayers + numreserves >= self.__size:
            return f"Mixed starting, get online!\n" \
                   f"{players}\n" \
                   f"Reserves, we need you!\n" \
                   f"{reserves}"

        message = f"Not enough players, feel free to get online and try to get it started anyway!\n" \
                  f"{players}\n"

        if numreserves > 0:
            message += f"Reserves, feel free to join in.\n" \
                       f"{reserves}"

        return message

    @classmethod
    async def create(cls, bot: Bot, guild, data: dict, sync, remove):
        mixed = Mixed(bot, guild, data, sync, remove)
        await mixed.__init()
        return mixed
