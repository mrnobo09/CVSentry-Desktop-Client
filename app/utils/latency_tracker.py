import time
from typing import Dict, List

class LatencyTracker:
    def __init__(self):
        # { camera_id: { frame_id: start_time } }
        self._start_times: Dict[str, Dict[int, float]] = {}
        # { camera_id: [latencies] }
        self._latencies: Dict[str, List[float]] = {}
        self._last_log_time: Dict[str, float] = {}

    def mark_start(self, camera_id: str, frame_id: int):
        """Marks the point where the frame is ingested (Point A)."""
        if camera_id not in self._start_times:
            self._start_times[camera_id] = {}
        
        self._start_times[camera_id][frame_id] = time.perf_counter()
        
        # Cleanup to prevent memory leaks if frames are dropped
        if len(self._start_times[camera_id]) > 100:
            # Remove oldest (lowest frame_id)
            oldest_frame_id = min(self._start_times[camera_id].keys())
            del self._start_times[camera_id][oldest_frame_id]

    def mark_end(self, camera_id: str, frame_id: int):
        """Marks the point where the frame is yielded to output (Point B)."""
        if camera_id not in self._start_times or frame_id not in self._start_times[camera_id]:
            return
            
        start_time = self._start_times[camera_id].pop(frame_id)
        latency = time.perf_counter() - start_time
        
        if camera_id not in self._latencies:
            self._latencies[camera_id] = []
            self._last_log_time[camera_id] = time.perf_counter()
            
        self._latencies[camera_id].append(latency)
        
        now = time.perf_counter()
        if now - self._last_log_time[camera_id] >= 5.0:
            avg_latency = sum(self._latencies[camera_id]) / len(self._latencies[camera_id])
            print(f"⏱️ [app/{camera_id}] Pipeline Latency (A→B): {avg_latency*1000:.1f}ms (over {len(self._latencies[camera_id])} frames)")
            self._latencies[camera_id].clear()
            self._last_log_time[camera_id] = now

pipeline_tracker = LatencyTracker()
