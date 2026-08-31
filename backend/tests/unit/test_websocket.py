import asyncio

from app.services.coindcx.websocket import CoinDCXWebSocketClient, WebSocketStatus


class FakeSocket:
    def __init__(self):
        self.handlers = {}
        self.emitted = []
        self.connect_calls = 0
        self.connected = False
        self.owner = None

    def on(self, event, handler):
        self.handlers[event] = handler

    async def emit(self, event, payload):
        self.emitted.append((event, payload))

    async def connect(self, *_args, **_kwargs):
        self.connect_calls += 1
        if self.connect_calls == 1:
            raise ConnectionError("first connection fails")
        self.connected = True
        await self.handlers["connect"]()

    async def wait(self):
        self.owner._stop = True

    async def disconnect(self):
        self.connected = False
        await self.handlers["disconnect"]()


async def test_websocket_reconnects_and_deduplicates_subscriptions():
    socket = FakeSocket()

    async def sleeper(_delay):
        await asyncio.sleep(0)

    client = CoinDCXWebSocketClient(
        "wss://stream.test", socket=socket, sleeper=sleeper, stale_after_seconds=999
    )
    socket.owner = client
    await client.subscribe_current_prices()
    await client.subscribe_current_prices()
    await client.run_forever()
    assert socket.connect_calls == 2
    joins = [event for event in socket.emitted if event[0] == "join"]
    assert len(joins) == 1
    assert client.status == WebSocketStatus.STOPPED


async def test_malformed_websocket_message_is_isolated():
    socket = FakeSocket()
    client = CoinDCXWebSocketClient("wss://stream.test", socket=socket)
    await client._on_trade({"data": {"bad": "payload"}})
    assert client.last_message_at is None
