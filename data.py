import json
import os


class ScrimbotData:

    def __init__(self):
        with open('bot.token', 'r') as file:
            self.token = file.read().strip()

        try:
            with open('data.json', 'r') as file:
                self.data = json.load(file)
        except FileNotFoundError:
            print("data file not found, initialising")
            self.data = {}
        except:
            os.rename('data.json', 'baddata.json')
            self.data = {}

    def sync(self):
        with open('data.json', 'w') as jsonfile:
            json.dump(self.data, jsonfile)

    def get_notes(self, guild) -> list:
        guild = str(guild)
        if guild not in self.data:
            self.data[guild] = {}
        if "notes" not in self.data[guild]:
            self.data[guild]["notes"] = []
        return self.data[guild]["notes"]

    def warnings(self, guild, member):
        return [d for d in self.get_notes(guild) if 'warning' in d and d['user'] == member]