from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from loguru import logger


class ManagedBot(Protocol):
    async def run(self) -> None: ...

    async def stop(self) -> None: ...


@dataclass(frozen=True)
class BotStatus:
    room_name: str
    trusted_identity: str
    running: bool


class InMemoryBotManager:
    def __init__(
        self,
        factory: Callable[[str, str], ManagedBot],
    ) -> None:
        self._factory = factory
        self._bots: dict[str, tuple[str, ManagedBot, asyncio.Task[None]]] = {}

    async def start(self, *, room_name: str, trusted_identity: str) -> BotStatus:
        current = self._bots.get(room_name)
        if current is not None:
            _, bot, task = current
            await bot.stop()
            try:
                await task
            except Exception:
                logger.exception("trusted leg bot failed during restart", room_name=room_name)

        sentinel = _PendingBot()

        async def run_bot() -> None:
            try:
                bot = self._factory(room_name, trusted_identity)
                self._bots[room_name] = (trusted_identity, bot, task)
                await bot.run()
            except Exception:
                logger.exception("trusted leg bot failed", room_name=room_name)
                raise

        task = asyncio.create_task(run_bot(), name=f"trusted-leg-bot:{room_name}")
        self._bots[room_name] = (trusted_identity, sentinel, task)
        task.add_done_callback(lambda _: self._bots.pop(room_name, None))
        return BotStatus(
            room_name=room_name,
            trusted_identity=trusted_identity,
            running=True,
        )

    async def stop(self, *, room_name: str) -> None:
        current = self._bots.get(room_name)
        if current is None:
            return
        _, bot, task = current
        await bot.stop()
        await task

    def status(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for room_name, (trusted_identity, _, task) in self._bots.items():
            result.append(
                {
                    "room_name": room_name,
                    "trusted_identity": trusted_identity,
                    "running": not task.done(),
                }
            )
        result.sort(key=lambda item: str(item["room_name"]))
        return result


class _PendingBot:
    async def run(self) -> None:
        return None

    async def stop(self) -> None:
        return None
