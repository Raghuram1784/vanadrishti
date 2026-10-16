import asyncio
from contextlib import suppress
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
ALLOWED_HOSTS = ('localhost', '127.0.0.1', '192.168.', '10.', '172.')


@router.websocket('/ws/events')
async def live_events(socket: WebSocket):
    origin = socket.headers.get('origin')
    if origin and not any(h in origin for h in ALLOWED_HOSTS):
        await socket.close(code=1008)
        return
    await socket.accept()
    hub = socket.app.state.live
    queue = asyncio.Queue(maxsize=100)
    hub.clients[socket] = queue
    await socket.send_json({'type': 'connection.ready', 'data': {'resync': True}})

    async def send():
        while True:
            message = await queue.get()
            if message is None:
                await socket.close(code=1013)
                return
            await socket.send_json(message)

    async def receive():
        while True:
            text = await socket.receive_text()
            if text == 'ping' and not queue.full():
                queue.put_nowait({'type': 'connection.pong', 'data': {}})

    tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.clients.pop(socket, None)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await task
