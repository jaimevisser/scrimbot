from datetime import tzinfo, datetime

from scrimbot import tag


class Scrim:
    def __init__(self, data: dict, timezone: tzinfo, sync):
        self.data = data
        self.id = data["thread"]
        self.size = 8
        self.time = datetime.fromtimestamp(data["time"], timezone)
        self.role = self.data["role"]
        self.author = self.data["author"]
        self.__sync = sync
        self.full = False

        if "players" not in self.data:
            self.data["players"] = []

        if "reserve" not in self.data:
            self.data["reserve"] = []

    def num_players(self):
        return len(self.data["players"])

    def num_reserves(self):
        return len(self.data["reserve"])

    def get_next_reserve(self):
        for r in self.data["reserve"]:
            if "called" not in r:
                return r
        return None

    def contains_user(self, user: int) -> bool:
        return self.contains_player(user) or self.contains_reserve(user)

    def contains_player(self, user: int) -> bool:
        return any(u["id"] == user for u in self.data["players"])

    def contains_reserve(self, user: int) -> bool:
        return any(u["id"] == user for u in self.data["reserve"])

    def add_player(self, player):
        self.data["players"].append(player)
        self.full = self.num_players() == self.size
        self.__sync()
        self.remove_reserve(player["id"])

    def remove_player(self, player_id):
        self.__remove_from_playerlist("players", player_id)
        self.full = self.num_players() == self.size
        if not self.full:
            auto = None
            for r in self.data["reserve"]:
                if "auto" in r:
                    auto = r
                    break

            if auto is not None:
                if "auto" in auto:
                    del auto["auto"]
                self.add_player(auto)

    def add_reserve(self, reserve):
        self.data["reserve"].append(reserve)
        self.__sync()
        self.remove_player(reserve["id"])

    def remove_reserve(self, player_id):
        self.__remove_from_playerlist("reserve", player_id)

    def set_auto_join(self, user, auto=True):
        for player in self.data["reserve"]:
            if player["id"] == user:
                if auto:
                    player["auto"] = True
                elif "auto" in player:
                    del player["auto"]
                self.__sync()
                break

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
            self.__sync()

    def generate_header_message(self) -> str:
        count = ""
        if self.num_players() > 0:
            count = f"**({self.num_players()}/{self.size})** "

        return f"{tag.role(self.role)}! Scrim at {self.scrim_time()} {count}" \
               f"started by {tag.user(self.author['id'])}\n"

    def generate_broadcast_listing(self) -> str:
        full = " **FULL**" if self.num_players() == self.size else ""

        return f"{tag.time(self.time)} Scrim{full}"

    def generate_player_list(self) -> str:
        message = ""
        for player in self.data["players"]:
            message += f"{player['mention']}\n"
        return message

    def generate_reserve_list(self) -> str:
        message = ""
        for player in self.data["reserve"]:
            extra = ""
            if "auto" in player and "started" not in self.data:
                extra = " (auto-join)"
            if "called" in player:
                extra = " (called)"
            message += f"{player['mention']}{extra}\n"
        return message

    def generate_content_message(self) -> str:
        message = ""
        if self.num_players() > 0:
            players = self.num_players()
            maxplayers = self.size
            message += f"\n**Players ({players}/{maxplayers})**\n"
            for player in self.data["players"]:
                message += f"- {player['mention']}\n"

        if self.num_reserves() > 0:
            reserves = self.num_reserves()
            message += f"\n**Reserves ({reserves})**\n"
            for player in self.data["reserve"]:
                extra = ""
                if "auto" in player and "started" not in self.data:
                    extra = "(auto-join)"
                if "called" in player:
                    extra = "(called)"
                message += f"- {tag.user(player['id'])} {extra}\n"

        if message == "":
            message = "Nobody signed up yet."

        return message

    def generate_name(self) -> str:
        players = self.num_players()

        time = self.time.strftime("%H.%M")

        return f"{time} {players}"

    def generate_start_message(self) -> str:
        if self.num_players() == 0:
            return "Sad moment, nobody signed up! Archiving the thread."

        players = ""
        numplayers = self.num_players()
        reserves = ""
        numreserves = self.num_reserves()

        for player in self.data["players"]:
            players += f"{tag.user(player['id'])} "

        for player in self.data["reserve"]:
            reserves += f"{tag.user(player['id'])} "

        if numplayers == self.size:
            return f"Scrim starting, get online!\n" \
                   f"{players}"

        if numplayers + numreserves >= self.size:
            return f"Scrim starting, get online!\n" \
                   f"{players}\n" \
                   f"Reserves, we need you!\n" \
                   f"{reserves}"

        message = f"Not enough players, feel free to get online and try to get it started anyway!\n" \
                  f"{players}\n"

        if numreserves > 0:
            message += f"Reserves, feel free to join in.\n" \
                       f"{reserves}"

        shortage = self.size - numplayers + numreserves
        if shortage <= 2:
            message += f"\n{tag.role(self.role)}, you might be able to make this a full scrim.\n" \
                       f"We need at least {shortage} player(s)."

        return message

    def scrim_time(self, separator = " / "):
        s = self.time.strftime("%H:%M")
        l = tag.time(self.time)
        return f"{s} (server){separator}{l} (your local time)"
