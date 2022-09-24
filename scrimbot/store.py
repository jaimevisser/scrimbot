import json
import os
from typing import Generic, TypeVar

T = TypeVar('T')


class Store(Generic[T]):

    def __init__(self, file: str, empty: T):
        self.__file = file
        self.__empty = empty
        self.data: T = self.__load()

    @property
    def file(self):
        return self.__file

    def __load(self) -> T:
        try:
            with open(self.__file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"'{self.__file}' not found, initialising")
            return self.__empty
        except:
            os.rename(self.__file, f"{self.__file}.bad")
            return self.__empty

    def sync(self):
        with open(self.__file, 'w') as jsonfile:
            json.dump(self.data, jsonfile, indent=4)
