import json


class Config:

    def __init__(self):
        self.guilds = []

        with open('data/bot.token', 'r') as file:
            self.token = file.read().strip()

        with open('data/config.json', 'r') as file:
            self.config = json.load(file)

        for g in self.config.keys():
            self.guilds.append(int(g))
