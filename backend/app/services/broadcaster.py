"""In-process WebSocket fan-out for dashboard alerts (SOS, etc.).

Single-process prototype: connected sockets live here. A multi-replica
deployment would replace this with Redis pub/sub — stretch goal.
"""

_connections: set = set()


async def register(ws) -> None:
    _connections.add(ws)


async def unregister(ws) -> None:
    _connections.discard(ws)


def connection_count() -> int:
    return len(_connections)


async def broadcast(kind: str, payload: dict) -> int:
    """Send to every subscriber. Returns number of sockets reached."""
    dead = []
    sent = 0
    for ws in list(_connections):
        try:
            await ws.send_json({"kind": kind, **payload})
            sent += 1
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.discard(ws)
    return sent
