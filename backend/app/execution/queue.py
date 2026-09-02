import asyncio
from enum import IntEnum
from itertools import count


class ExecutionPriority(IntEnum):
    EMERGENCY = 0
    PROTECTION = 1
    EXIT = 2
    RECONCILIATION = 3
    ENTRY = 4


class LiveExecutionQueue:
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._sequence = count()

    async def put(self, priority: ExecutionPriority, operation):
        await self._queue.put((int(priority), next(self._sequence), operation))

    async def get(self):
        _, _, operation = await self._queue.get()
        return operation
