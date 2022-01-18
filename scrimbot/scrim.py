from datetime import tzinfo, datetime

from scrimbot import tag


class Scrim:
    def __init__(self, data: dict, timezone: tzinfo, sync):
        self.data = data
        self.id = data["thread"]
        self.size = 8
        self.time = datetime.fromtimestamp(data["time"], timezone)
        self.role = self.data["role"]
        self.creator = self.data["creator"]
        self.__sync = sync

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

    def contains_player(self, user: int) -> bool:
        for x in self.data["players"]:
            if x["id"] == user:
                return True

        for x in self.data["reserve"]:
            if x["id"] == user:
                return True

        return False

    def remove_player(self, player_id):
        self.__remove_from_playerlist("players", player_id)
        if self.num_players() < self.size:
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

    def generate_header_message(self) -> str:
        count = ""
        if self.num_players() > 0:
            count = f"**({self.num_players()}/{self.size})** "

        return f"{tag.role(self.role)}! Scrim at {tag.time(self.time)} {count}" \
               f"started by {tag.user(self.creator)}\n"

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
