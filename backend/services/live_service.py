"""Bounded, process-local broadcasts. REST remains the durable source of truth."""
import asyncio
import logging


class LiveHub:
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.clients = {}

    def publish(self, messages):
        # Called from FastAPI worker threads only after a SQLite commit.
        if not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._enqueue, messages)

    def _enqueue(self, messages):
        for queue in list(self.clients.values()):
            for message in messages:
                if queue.full():
                    # A slow client must reconnect and resync via REST.
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(None)
                    break
                queue.put_nowait(message)

    async def close(self):
        for socket in list(self.clients):
            try:
                await socket.close(code=1001)
            except Exception:
                logging.getLogger(__name__).debug('Socket already closed')
