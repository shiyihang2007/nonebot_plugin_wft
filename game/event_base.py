"""事件分发器：支持优先级与锁/解锁触发。

设计目标（来自手写流程图）：

- 事件触发（`active`）：按优先级从高到低依次执行监听器。
- 事件锁/解锁（`lock`/`unlock`）：用一个简单计数器表示“阻塞点”。
  - `lock()`：计数 +1
  - `unlock()`：计数 -1（不小于 0）
  - 当计数变为 0 时，会以最近一次 `unlock()` 传入的参数触发 `active()`。

这样可以表达“等待玩家输入”的流程：在进入等待前对下一事件 `lock()`，玩家操作完成后对该事件
`unlock()`，从而推进流程。
"""

from __future__ import annotations

from typing import Any

from .listener import Listener


class EventBase:
    """单个事件：监听器 + 优先级 + 锁计数。"""

    def __init__(self) -> None:
        self._listeners: list[tuple[int, Listener]] = []
        self._lock_count: int = 0
        self._pending_trigger: tuple[Any, str | None, list[str]] | None = None

    @property
    def lock_count(self) -> int:
        """当前锁计数（0 表示未锁定）。"""
        return self._lock_count

    def add_listener(self, listener: Listener, priority: int = 0) -> None:
        """添加监听器。

        约束：
        - 优先级范围为 [-10, 10]
        - 触发时按优先级从大到小依次调用
        - 同一优先级下的调用顺序不保证
        """
        if not isinstance(priority, int):
            raise TypeError("priority 必须为 int")
        if priority < -10 or priority > 10:
            raise ValueError("priority 必须在 [-10, 10] 范围内")
        self._listeners.append((priority, listener))

    def remove_listener(self, listener: Listener) -> None:
        """移除监听器（按对象身份匹配）。"""
        self._listeners = [(p, l) for (p, l) in self._listeners if l is not listener]

    async def active(self, room: Any, user_id: str | None, args: list[str]) -> None:
        """强制触发事件：无视锁状态，立即执行监听器。"""
        for _, listener in sorted(self._listeners, key=lambda x: x[0], reverse=True):
            await listener(room, user_id, args)

    def lock(self) -> None:
        """加锁：计数 +1。"""
        self._lock_count += 1

    async def unlock(
        self, room: Any, user_id: str | None = None, args: list[str] | None = None
    ) -> None:
        """解锁：计数 -1，并在计数归零时触发事件。

        - 若当前计数为 0，`unlock()` 仍会触发事件（用于“直接推进”的场景）。
        - 若计数在本次调用后仍大于 0，则仅记录“待触发参数”，不执行监听器。
        """
        if args is None:
            args = []

        if self._lock_count > 0:
            self._lock_count -= 1

        self._pending_trigger = (room, user_id, args)
        if self._lock_count != 0 or not self._pending_trigger:
            return

        pending = self._pending_trigger
        self._pending_trigger = None
        await self.active(pending[0], pending[1], pending[2])
