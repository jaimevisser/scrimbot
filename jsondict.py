import json


class JsonDict(dict):

    def __init__(self, folder):
        super().__init__()
        self.__folder = folder

    def __getitem__(self, key):
        if key not in self:
            return self.__load(key)
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        __save(key, value)

    def __load(self, key):
        with open(self.__folder + "/" + key + ".json") as jsonfile:
            data = json.load(jsonfile)
            self[key] = data
