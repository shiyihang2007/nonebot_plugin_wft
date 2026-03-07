from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from game.event_base import EventBase


@pytest.mark.unit
def test_add_listener__priority_type_must_be_int() -> None:
    event = EventBase("x")

    async def listener(room, user_id, args):
        return None

    with pytest.raises(TypeError):
        event.add_listener(listener, priority="1")


@pytest.mark.unit
def test_add_listener__priority_range_must_be_valid() -> None:
    event = EventBase("x")

    async def listener(room, user_id, args):
        return None

    with pytest.raises(ValueError):
        event.add_listener(listener, priority=11)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_active__listeners_run_by_desc_priority() -> None:
    event = EventBase("x")
    order: list[str] = []

    async def low(room, user_id, args):
        order.append("low")

    async def high(room, user_id, args):
        order.append("high")

    async def mid(room, user_id, args):
        order.append("mid")

    event.add_listener(low, priority=-1)
    event.add_listener(high, priority=2)
    event.add_listener(mid, priority=1)

    await event.active(object(), "u1", ["a"])
    assert order == ["high", "mid", "low"]


@pytest.mark.unit
def test_remove_listener__remove_by_identity() -> None:
    event = EventBase("x")

    async def listener_a(room, user_id, args):
        return None

    async def listener_b(room, user_id, args):
        return None

    event.add_listener(listener_a)
    event.add_listener(listener_b)
    event.remove_listener(listener_a)

    assert len(event._listeners) == 1
    assert event._listeners[0][1] is listener_b


@pytest.mark.unit
def test_lock_and_lock_count__increments() -> None:
    event = EventBase("x")
    assert event.lock_count == 0

    event.lock()
    event.lock()

    assert event.lock_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unlock__decrement_without_trigger_when_still_locked() -> None:
    event = EventBase("x")
    listener = AsyncMock()
    event.add_listener(listener)
    event.lock()
    event.lock()

    await event.unlock(object(), "u1", [])

    assert event.lock_count == 1
    listener.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unlock__trigger_when_count_reaches_zero() -> None:
    event = EventBase("x")
    listener = AsyncMock()
    event.add_listener(listener)
    event.lock()

    await event.unlock("room", "u1", ["p"])

    assert event.lock_count == 0
    listener.assert_awaited_once_with("room", "u1", ["p"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unlock__not_locked_only_logs_warning(caplog) -> None:
    event = EventBase("x")
    listener = AsyncMock()
    event.add_listener(listener)

    with caplog.at_level("WARNING"):
        await event.unlock("room", "u2", ["p2"])

    listener.assert_not_awaited()
    assert "尝试解锁未上锁的事件" in caplog.text
