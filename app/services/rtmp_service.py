import asyncio
import os
from typing import List, Dict
from utils.redis_manager import redis_manager as rdb
from services.frame_aggregator import frame_aggregator
from utils.rtmp_streamer import RTMPStreamer
from services.threat_manager import threat_manager
from routes.node_routes import send_threat_alert
from utils.latency_tracker import pipeline_tracker

SRS_BASE_URL = os.getenv("SRS_BASE_URL", "rtmp://localhost/live")

_active_stream_tasks: Dict[str, asyncio.Task] = {}

# Log every Nth frame sent to SRS to avoid console flood
LOG_EVERY_N_FRAMES = 30


async def start_rtmp_broadcasting(camera_ids: List[str]):
    """
    Consumes annotated frames from the aggregator and pushes them to SRS via RTMP.
    """
    streamers: Dict[str, RTMPStreamer] = {}
    frames_sent: Dict[str, int] = {cam_id: 0 for cam_id in camera_ids}

    print(f"[app/rtmp] 🚀 Initialising RTMP broadcast for: {camera_ids}")

    for cam_id in camera_ids:
        stream_url = f"{SRS_BASE_URL}/{cam_id}"
        print(f"[app/rtmp] 📡 Starting stream → {stream_url}")
        streamers[cam_id] = RTMPStreamer(stream_url)   # fps=10, 360p — set in RTMPStreamer
        streamers[cam_id].start()

 
    try:
        async for data in frame_aggregator(rdb, camera_ids):
            target_cam = data['camera_id']
            frame_bytes = data['frame_bytes']

            if target_cam in streamers:
                streamers[target_cam].write(frame_bytes)

                frame_id = data.get('frame_id')
                if frame_id is not None:
                    pipeline_tracker.mark_end(target_cam, frame_id)

                frames_sent[target_cam] += 1
                n = frames_sent[target_cam]

                if getattr(data, 'get', None):
                    # Feed metadata into ThreatManager for 30s sliding window deduplication
                    asyncio.create_task(
                        threat_manager.process_frame(
                            camera_id=target_cam,
                            frame_id=data.get('frame_id', -1),
                            is_aiming=data.get('is_aiming', False),
                            has_weapon=data.get('has_weapon', False),
                            number_of_guns=data.get('number_of_guns', 0),
                            face_identities=data.get('face_identities', [])
                        )
                    )

                    if n % LOG_EVERY_N_FRAMES == 0:
                        print(
                            f"[app/{target_cam}] 📺 {n} frames sent to SRS "
                            f"(frame_id={data.get('frame_id')}, size={len(frame_bytes)} bytes)"
                        )

    except asyncio.CancelledError:
        print("[app/rtmp] 🛑 RTMP Service cancelled.")
    except Exception as e:
        print(f"[app/rtmp] 🔥 RTMP Service error: {e}")
    finally:
        print("[app/rtmp] Cleaning up RTMP processes...")
        for s in streamers.values():
            s.stop()