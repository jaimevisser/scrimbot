import json
from os.path import exists

import yaml


class Config:

    def __init__(self):
        self.guilds = []
        self.config = None

        with open('data/bot.token', 'r') as file:
            self.token = file.read().strip()

        if exists('data/config.json'):
            with open('data/config.json', 'r') as file:
                self.config = json.load(file)

        if exists('data/config.yaml'):
            with open('data/config.yaml', 'r') as file:
                self.config = yaml.safe_load(file)

        if self.config is None:
            raise FileNotFoundError()

        for g in self.config.keys():
            self.guilds.append(int(g))
