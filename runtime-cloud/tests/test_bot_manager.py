import asyncio

from runtime_cloud_service.bot_manager import InMemoryBotManager


class _FakeBot:
    def __init__(self) -> None:
        self.run_calls = 0
        self.stop_calls = 0
        self.started = asyncio.Event()
        self.released = asyncio.Event()

    async def run(self) -> None:
        self.run_calls += 1
        self.started.set()
        await self.released.wait()

    async def stop(self) -> None:
        self.stop_calls += 1
        self.released.set()


def test_manager_starts_bot_once_per_room() -> None:
    async def run_test() -> None:
        fake_bot = _FakeBot()
        manager = InMemoryBotManager(lambda room_name, trusted_identity: fake_bot)

        first = await manager.start(room_name="call-main", trusted_identity="trusted-matt")
        await fake_bot.started.wait()
        second = await manager.start(room_name="call-main", trusted_identity="trusted-matt")

        assert first.room_name == "call-main"
        assert first.running is True
        assert second.running is True
        assert fake_bot.run_calls == 1

        await manager.stop(room_name="call-main")

    asyncio.run(run_test())


def test_manager_reports_room_status() -> None:
    async def run_test() -> None:
        fake_bot = _FakeBot()
        manager = InMemoryBotManager(lambda room_name, trusted_identity: fake_bot)

        await manager.start(room_name="call-main", trusted_identity="trusted-matt")
        await fake_bot.started.wait()

        status = manager.status()

        assert status == [
            {
                "room_name": "call-main",
                "trusted_identity": "trusted-matt",
                "running": True,
            }
        ]

        await manager.stop(room_name="call-main")

    asyncio.run(run_test())


def test_manager_restarts_existing_room_bot() -> None:
    async def run_test() -> None:
        first_bot = _FakeBot()
        second_bot = _FakeBot()
        bots = iter([first_bot, second_bot])
        manager = InMemoryBotManager(lambda room_name, trusted_identity: next(bots))

        await manager.start(room_name="call-main", trusted_identity="trusted-matt")
        await first_bot.started.wait()

        restarted = await manager.start(room_name="call-main", trusted_identity="trusted-matt")
        await second_bot.started.wait()

        assert restarted.running is True
        assert first_bot.stop_calls == 1
        assert second_bot.run_calls == 1

        await manager.stop(room_name="call-main")

    asyncio.run(run_test())
