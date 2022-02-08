import json
from os.path import exists

import yaml


class Config:
    ALL_FEATURES = {"TIME", "LOG", "SCRIMS", "REPORT"}

    def __init__(self):
        self.guilds: list[int] = []
        self.config: dict[str, dict]
        self.__features: dict[int, set[str]] = {}

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

        for k, v in self.config.items():
            self.__features[int(k)] = set(v.get("features", Config.ALL_FEATURES))

    def guilds_with_features(self, features: set[str]) -> list[int]:
        return list(k for k, v in self.__features.items() if v.issuperset(features))
