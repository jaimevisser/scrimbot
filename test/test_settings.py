import unittest
from unittest import TestCase
from unittest.mock import MagicMock

from scrimbot import Settings
from scrimbot.settings import ParseException


class SettingsTests(TestCase):

    @staticmethod
    def create_settings(store=MagicMock()):
        store.file = "testfile"
        return Settings(store, lambda: {0, 1, 2}, lambda: {10, 11})

    def test_get_filename(self):

        file = self.create_settings().get_filename()

        self.assertEqual("testfile", file)

    INVALID_INPUT = {
        "no server": {},
        "channel not a dict": {"server": {"timezone": "UTC"}, "channel": "not a dict"},
        "invalid key in server": {"server": {"timezone": "UTC", "invalid_key": "something"}},
        "missing required settings": {"server": {}},
        "invalid timezone": {"server": {"timezone": "Honolulu"}},
        "invalid role": {"server": {"timezone": "UTC"}, "channel_defaults": {"scrimmer_role": 12}},
        "invalid top level key": {"server": {"timezone": "UTC"}, "weird_key": "something"},
        "invalid channel": {"server": {"timezone": "UTC"}, "channel_defaults": {"broadcast_channel": 5}},
        "invalid int": {"server": {"timezone": "UTC"}, "channel_defaults": {"ping_cooldown": "just a string"}},
        "invalid string": {"server": {"timezone": "UTC"}, "channel_defaults": {"prefix": 20}},
    }

    def test_replace_invalid_input(self):
        for k, testdata in self.INVALID_INPUT.items():
            store = MagicMock()
            with self.subTest(msg=k):
                with self.assertRaises(ParseException):
                    self.create_settings(store).replace(testdata)
                assert not store.data.clear.called
                assert not store.data.update.called
                assert not store.sync.called

    VALID_INPUT = {
        "minimal valid input": {"server": {"timezone": "Atlantic/Madeira"}},
        "valid role": {"server": {"timezone": "UTC"}, "channel_defaults": {"scrimmer_role": 10}},
        "valid channel": {"server": {"timezone": "UTC"}, "channel_defaults": {"broadcast_channel": 1}},
        "valid int": {"server": {"timezone": "UTC"}, "channel_defaults": {"ping_cooldown": 20}},
        "valid string": {"server": {"timezone": "UTC"}, "channel_defaults": {"prefix": "Scrimmage"}},
    }

    def test_replace_valid_input(self):
        for k, testdata in self.VALID_INPUT.items():
            store = MagicMock()
            with self.subTest(msg=k):
                self.create_settings(store).replace(testdata)
                assert store.data.clear.called
                assert store.data.update.called
                assert store.sync.called

                args = store.data.update.call_args.args

                self.assertDictEqual(args[0], testdata)

    def test_get_server_settings(self):
        store = MagicMock()
        store.data = {"server": {"timezone": "Atlantic/Madeira"}}

        server = self.create_settings(store).server

        self.assertDictEqual(server, {'timezone': 'Atlantic/Madeira', 'reports_per_day': 2})

    def test_get_channel_default_settings(self):
        store = MagicMock()
        store.data = {"server": {"timezone": "Atlantic/Madeira"}}

        server = self.create_settings(store).channel(20)

        self.assertDictEqual(server, {'ping_cooldown': 5, 'prefix': 'Mixed Scrim'})

    def test_get_channel_settings(self):
        store = MagicMock()
        store.data = {"server": {"timezone": "Atlantic/Madeira"}, 'channel': {'20': {'broadcast_channel': 45}}}

        channel = self.create_settings(store).channel(20)

        self.assertDictEqual(channel, {'broadcast_channel': 45, 'ping_cooldown': 5, 'prefix': 'Mixed Scrim'})

    def test_get_all_channel_settings(self):
        store = MagicMock()
        store.data = {"server": {"timezone": "Atlantic/Madeira"},
                      'channel': {'20': {'broadcast_channel': 45}, '25': {'broadcast_channel': 42}}}

        channels = self.create_settings(store).channels

        self.assertDictEqual(channels, {'20': {'broadcast_channel': 45, 'ping_cooldown': 5, 'prefix': 'Mixed Scrim'},
                                        '25': {'broadcast_channel': 42, 'ping_cooldown': 5, 'prefix': 'Mixed Scrim'}})

    def test_get_channel_defaults(self):
        store = MagicMock()
        store.data = {"server": {"timezone": "Atlantic/Madeira"}, 'channel_defaults': {'broadcast_channel': 40},
                      'channel': {'20': {'broadcast_channel': 45}}}

        channel = self.create_settings(store).channel_defaults

        self.assertDictEqual(channel, {'broadcast_channel': 40, 'ping_cooldown': 5, 'prefix': 'Mixed Scrim'})


if __name__ == '__main__':
    unittest.main()
