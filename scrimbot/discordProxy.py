import logging
from typing import TypeVar, Generic, Callable, Optional, Coroutine, Any

import discord

T = TypeVar('T')
R = TypeVar('R')

_log = logging.getLogger(__name__)


class DiscordProxy(Generic[T]):

    @classmethod
    def error_handler_silent(cls, error: discord.HTTPException) -> bool:
        return True

    def __init__(self,
                 fetcher: Optional[Callable[..., Coroutine[Any, Any, T]]] = None,
                 on_fetch: Optional[Callable[[T], Coroutine[Any, Any, Any]]] = None,
                 handle_error: Optional[Callable[[discord.HTTPException], bool]] = None) -> None:
        self.__fetcher: Optional[Callable[..., Coroutine[Any, Any, T]]] = fetcher
        self.__on_fetch: Optional[Callable[[T], Coroutine[Any, Any, Any]]] = on_fetch
        self.error_handler = handle_error
        self.content: Optional[T] = None

    async def fetch(self, fetcher: Optional[Callable[..., Coroutine[Any, Any, T]]] = None) -> bool:
        if fetcher is not None:
            self.__fetcher = fetcher
        if self.content is None:
            if self.__fetcher is not None:
                try:
                    self.content = await self.__fetcher()
                except discord.HTTPException as error:
                    self.__handle_error(error)
            if self.content is not None and self.__on_fetch is not None:
                await self.__on_fetch(self.content)
        return self.content is not None

    async def map(self, mapper: Callable[[T], R]) -> Optional[R]:
        if await self.fetch():
            try:
                return mapper(self.content)
            except discord.HTTPException as error:
                self.__handle_error(error)

    async def wait(self, coro_generator: Callable[[T], Coroutine[Any, Any, R]]) -> Optional[R]:
        if await self.fetch():
            try:
                return await coro_generator(self.content)
            except discord.HTTPException as error:
                self.__handle_error(error)

    def __handle_error(self, error: discord.HTTPException):
        if self.error_handler is not None and self.error_handler(error):
            return
        _log.error("Caught error during discord operation")
        _log.exception(error)
