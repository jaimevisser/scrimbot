import os
import unittest

from ..jsondict import JsonDict


class MyTestCase(unittest.TestCase):
    __folder = "tests"

    def setUp(self):
        os.makedirs(self.__folder)
        self.__subject = JsonDict(self.__folder)

    def tearDown(self):
        os.removedirs(self.__folder)

    def test_add(self):
        self.__subject.put


if __name__ == '__main__':
    unittest.main()
