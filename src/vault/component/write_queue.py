import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import PrivateAttr

from common.model import MutableModel

ResultT = TypeVar("ResultT")


class VaultWriteQueue(MutableModel):
    """Serialize vault mutations through one async lock."""

    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def run(self, operation: Callable[[], Awaitable[ResultT]]) -> ResultT:
        async with self._lock:
            return await operation()
