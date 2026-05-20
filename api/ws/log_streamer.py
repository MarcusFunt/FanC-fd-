from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


class LogStreamer:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._buffers: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=50_000)
        )
        self._lock = asyncio.Lock()

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[job_id].add(websocket)
            replay = list(self._buffers[job_id])
        for message in replay:
            await websocket.send_json(message)

    async def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[job_id].discard(websocket)

    async def publish(self, job_id: str, message: dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **message,
        }
        async with self._lock:
            self._buffers[job_id].append(payload)
            connections = list(self._connections[job_id])

        stale: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections[job_id].discard(websocket)


log_streamer = LogStreamer()


@router.websocket("/ws/jobs/{job_id}/logs")
async def stream_job_logs(websocket: WebSocket, job_id: str) -> None:
    await log_streamer.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await log_streamer.disconnect(job_id, websocket)
