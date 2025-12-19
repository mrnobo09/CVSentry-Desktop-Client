import time
#import asyncio
from typing import Dict, Optional, Tuple, Any

# CONFIGURATION
FRAME_TTL = 5.0  # Seconds before a frame is deleted if not retrieved
CLEANUP_INTERVAL = 100  # Run cleanup every N insertions to save CPU

class FrameCache:
    def __init__(self):
        # { camera_id: { frame_id: (timestamp, frame_bytes) } }
        self._store: Dict[str, Dict[int, Tuple[float, bytes]]] = {}
        self._counter = 0

    def add(self, camera_id: str, frame_id: int, frame: bytes):
        """Stores a frame locally."""
        if camera_id not in self._store:
            self._store[camera_id] = {}
        
        # Store with current timestamp for TTL
        self._store[camera_id][frame_id] = (time.time(), frame)
        
        # Periodic cleanup 
        self._counter += 1
        if self._counter >= CLEANUP_INTERVAL:
            self._cleanup()
            self._counter = 0

    def get(self, camera_id: str, frame_id: int) -> Optional[bytes]:
        """Retrieves and REMOVES the frame (Atomic Pop)."""
        if camera_id in self._store and frame_id in self._store[camera_id]:
            _, frame = self._store[camera_id].pop(frame_id)
            return frame
        return None

    def _cleanup(self):
        """Removes expired frames to prevent memory leaks."""
        now = time.time()
        for cam_id in list(self._store.keys()):
            # Find frames older than FRAME_TTL
            expired_ids = [
                fid for fid, (ts, _) in self._store[cam_id].items() 
                if now - ts > FRAME_TTL
            ]
            
            for fid in expired_ids:
                del self._store[cam_id][fid]
                # print(f"⚠️ Frame {fid} for {cam_id} expired and was dropped.")


frame_cache = FrameCache()