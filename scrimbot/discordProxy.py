from typing import TypeVar, Generic, Callable, Optional, Coroutine, Any

T = TypeVar('T')
R = TypeVar('R')


class DiscordProxy(Generic[T]):

    def __init__(self,
                 fetcher: Optional[Callable[..., Coroutine[Any, Any, T]]] = None,
                 on_fetch: Optional[Callable[[T], Coroutine[Any, Any, Any]]] = None) -> None:
        self.__fetcher: Optional[Callable[..., Coroutine[Any, Any, T]]] = fetcher
        self.__on_fetch: Optional[Callable[[T], Coroutine[Any, Any, Any]]] = on_fetch
        self.content: Optional[T] = None

    async def fetch(self, fetcher: Optional[Callable[..., Coroutine[Any, Any, T]]] = None) -> bool:
        if fetcher is not None:
            self.__fetcher = fetcher
        if self.content is None:
            if self.__fetcher is not None:
                self.content = await self.__fetcher()
            if self.content is not None and self.__on_fetch is not None:
                await self.__on_fetch(self.content)
        return self.content is not None

    async def map(self, mapper: Callable[[T], R]) -> Optional[R]:
        if await self.fetch():
            return mapper(self.content)

        return None

    async def wait(self, coro_generator: Callable[[T], Coroutine[Any, Any, R]]) -> Optional[R]:
        if await self.fetch():
            return await coro_generator(self.content)

        return None
