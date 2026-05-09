import asyncio
import time
import requests
import os
from dependencies.state import _node_state

DJANGO_URL = os.getenv("DJANGO_URL", "http://localhost:8000")

MAX_BATCH_SIZE = 50
FLUSH_INTERVAL_SECONDS = 0.5


class MetadataDispatcher:
    def __init__(self, camera_id: str, srs_stream_id: str):
        self.camera_id = camera_id
        self.srs_stream_id = srs_stream_id
        self.buffer: list = []
        self.last_flush = time.time()
        self._lock = asyncio.Lock()

    async def add(self, frame_number: int, detections: dict, threat_meta: dict):
        async with self._lock:
            self.buffer.append({
                "frame_number": frame_number,
                "timestamp_micros": int(time.time() * 1_000_000),
                "detections": detections,
                "severity": threat_meta.get("severity", "normal"),
                "has_threat": threat_meta.get("has_threat", False),
            })

            if len(self.buffer) >= MAX_BATCH_SIZE:
                await self._flush_locked()

    async def flush(self):
        async with self._lock:
            await self._flush_locked()

    async def _flush_locked(self):
        if not self.buffer:
            return

        batch = list(self.buffer)
        self.buffer.clear()
        self.last_flush = time.time()

        token = _node_state.get("access_token")
        if not token:
            print(f"[metadata/{self.camera_id}] ⚠️ No access token, dropping {len(batch)} frames")
            return

        payload = {
            "camera_id": self.camera_id,
            "srs_stream_id": self.srs_stream_id,
            "frames": batch,
        }

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{DJANGO_URL}/api/v1/streams/metadata/batch/",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5,
                ),
            )
        except Exception as e:
            print(f"[metadata/{self.camera_id}] ❌ Batch dispatch failed: {e}")


class MetadataDispatcherManager:
    def __init__(self):
        self.dispatchers: dict = {}
        self._flush_task = None

    def get_or_create(self, camera_id: str, srs_stream_id: str) -> MetadataDispatcher:
        if camera_id not in self.dispatchers:
            self.dispatchers[camera_id] = MetadataDispatcher(camera_id, srs_stream_id)
        return self.dispatchers[camera_id]

    def remove(self, camera_id: str):
        self.dispatchers.pop(camera_id, None)

    async def start_periodic_flush(self):
        async def _loop():
            while True:
                await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
                for dispatcher in list(self.dispatchers.values()):
                    await dispatcher.flush()

        self._flush_task = asyncio.create_task(_loop())

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        for dispatcher in list(self.dispatchers.values()):
            await dispatcher.flush()


metadata_dispatcher_manager = MetadataDispatcherManager()
