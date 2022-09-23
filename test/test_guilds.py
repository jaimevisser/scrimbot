import unittest
from unittest.mock import MagicMock

import discord
from asynctest import patch, TestCase

import scrimbot
from scrimbot import Guild


class Guilds(TestCase):
    BOT = MagicMock(discord.Bot)

    @patch("scrimbot.Guild")
    async def test_create(self, guild_class):
        guilds = scrimbot.Guilds(self.BOT)
        created_guild = MagicMock(Guild)
        guild_class.return_value = created_guild

        guild = await guilds.get(42)

        self.assertIsNotNone(guild)
        guild_class.assert_called_with('42', self.BOT)
        created_guild.init.assert_called_once()

    @patch("scrimbot.Guild")
    async def test_guild_created_once(self, guild_class):
        guilds = scrimbot.Guilds(self.BOT)
        created_guild = MagicMock(Guild)
        guild_class.return_value = created_guild

        guild_one = await guilds.get(42)
        guild_two = await guilds.get(42)

        self.assertIsNotNone(guild_two)
        self.assertIs(guild_one, guild_two)
        guild_class.assert_called_once_with('42', self.BOT)


if __name__ == '__main__':
    unittest.main()
