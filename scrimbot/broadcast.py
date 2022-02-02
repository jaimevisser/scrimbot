import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord

from scrimbot import ScrimManager

_log = logging.getLogger(__name__)

class Broadcaster:

    def __init__(self, channel, guild):
        self.channel = channel
        self.guild = guild
        self.__channel: Optional[discord.abc.GuildChannel] = None
        self.__message: Optional[discord.abc.TextChannel] = None
        self.__invite: Optional[discord.Invite] = None
        self.__update_task: Optional[asyncio.Task] = None
        self.__edits = 0
        self.__start_time = datetime.now(timezone.utc)
        self.__edit_log: list[datetime] = []
        self.__content_hashes: set[str] = set("START")

    def __can_update(self):
        now = datetime.now(timezone.utc)
        limit = now - timedelta(hours=1)
        limit = max(limit, self.__start_time)
        max_updates = ((now - limit).seconds / (60 * 2))
        return len(self.__edit_log) < max_updates

    def __prune_editlog(self):
        now = datetime.now(timezone.utc)
        limit = now - timedelta(hours=1)
        self.__edit_log = list([t for t in self.__edit_log if t > limit])

    async def update(self):
        self.guild.queue_task(self.__update())

    async def __delayed_update(self):
        await asyncio.sleep(timedelta(minutes=1).seconds)
        self.__update_task = None
        await self.__update()

    async def __update(self):
        scrims: list[ScrimManager] = self.guild.scrims
        relevant_scrims: list[ScrimManager] = \
            list([s for s in scrims if s.broadcast == self.channel and s.scrim.time >= datetime.now(timezone.utc)])

        relevant_scrims.sort(key=lambda s: s.scrim.time)

        relevant_scrims = relevant_scrims[:10]

        bot: discord.Bot = self.guild.bot

        if self.__channel is None:
            self.__channel = await bot.fetch_channel(self.channel)

        if self.__message is None:
            async for message in self.__channel.history(limit=4):
                if message.author == self.guild.bot.user:
                    self.__message = message
                    self.__edits = 3
                    break

        new_content_hashes = set([str(s.id) + ("F" if s.scrim.full else "N") for s in relevant_scrims])

        if new_content_hashes == self.__content_hashes:
            return

        if not self.__can_update():
            if self.__update_task is None:
                _log.info(f"Updating broadcast for {self.channel} postponed")
                self.__update_task = self.guild.queue_task(self.__delayed_update())
            return

        if self.__invite is None:
            self.__invite = await self.guild.fetch_invite()

        content = []
        if self.__invite is not None:
            content.append(self.__invite.url)
        if len(relevant_scrims) == 0:
            content.append("No scrims planned at the moment.")

        content = "\n".join(content)

        self.__content_hashes = new_content_hashes
        embeds = list([s.create_link_embed() for s in relevant_scrims])

        _log.info(f"Updating broadcast {self.channel}")
        if self.__edits >= 3 or self.__message is None:
            if self.__message is not None:
                try:
                    await self.__message.delete()
                except discord.NotFound:
                    self.__message = None
            self.__message = await self.__channel.send(content=content, embeds=embeds)
            self.__edits = 0
            try:
                await self.__message.publish()
            except discord.DiscordException:
                pass
        else:
            try:
                await self.__message.edit(content=content, embeds=embeds)
                self.__edits += 1
            except discord.NotFound:
                self.__message = None

        self.__edit_log.append(datetime.now(timezone.utc))
        self.__prune_editlog()
