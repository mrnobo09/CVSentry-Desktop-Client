import asyncio
import os
import time
from typing import Dict

from services.frame_aggregator import frame_aggregator
from services.webrtc_streamer import WebrtcStreamer
from services.threat_manager import threat_manager
from services.metadata_dispatcher import metadata_dispatcher_manager
from utils.redis_manager import redis_manager as rdb
from utils.latency_tracker import pipeline_tracker
from routes.node_routes import send_threat_alert
from dependencies.state import _node_state

CLOUD_SRS_WHIP_URL = os.getenv("CLOUD_SRS_WHIP_URL", "http://srs:1985/rtc/v1/publish/")

LOG_EVERY_N_FRAMES = 30

_active_streams: Dict[str, WebrtcStreamer] = {}
_active_camera_ids: list = []


async def register_stream_on_cloud(camera_id: str) -> dict | None:
    import requests
    token = _node_state.get("access_token")
    local_ip = _node_state.get("local_ip")
    port = int(os.getenv("NODE_PORT", "8001"))
    if not token or not local_ip:
        print(f"[stream] ⚠️ Cannot register stream — node not registered")
        return None

    try:
        resp = requests.post(
            f"{os.getenv('DJANGO_URL', 'http://localhost:8000')}/api/v1/streams/register/",
            json={
                "camera_id": camera_id,
                "base_url": f"http://{local_ip}",
                "port": port,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            print(f"[stream] ✅ Stream registered: {data.get('srs_stream_id')}")
            return data
        print(f"[stream] ❌ Stream registration failed: {resp.status_code} {resp.text}")
        return None
    except Exception as e:
        print(f"[stream] ❌ Stream registration error: {e}")
        return None


async def start_streaming(camera_ids: list):
    global _active_camera_ids
    _active_camera_ids = list(camera_ids)

    streamers: Dict[str, WebrtcStreamer] = {}
    dispatchers: Dict[str, object] = {}
    frames_sent: Dict[str, int] = {cam_id: 0 for cam_id in camera_ids}

    token = _node_state.get("access_token")

    for cam_id in camera_ids:
        ws = WebrtcStreamer(cam_id)
        streamers[cam_id] = ws
        _active_streams[cam_id] = ws

        reg_data = await register_stream_on_cloud(cam_id)
        if reg_data:
            srs_stream_id = reg_data.get("srs_stream_id", "")
            srs_stream_url = reg_data.get("stream_url", f"webrtc://srs/live/{srs_stream_id}")
        else:
            srs_stream_id = f"{_node_state.get('user_id')}_{_node_state.get('node_id')}_{cam_id}"
            srs_stream_url = f"webrtc://srs/live/{srs_stream_id}"

        whip_url = CLOUD_SRS_WHIP_URL or "http://localhost:1985/rtc/v1/publish/"

        await ws.start_cloud_relay(whip_url, srs_stream_url, token)

        dispatcher = metadata_dispatcher_manager.get_or_create(cam_id, srs_stream_id=srs_stream_id)
        dispatchers[cam_id] = dispatcher

        print(f"[stream/{cam_id}] 🚀 Streaming active (local WebRTC + cloud relay)")

    try:
        async for data in frame_aggregator(rdb, camera_ids):
            target_cam = data["camera_id"]
            jpeg_bytes = data["jpeg_bytes"]
            frame_id = data.get("frame_id", 0)
            detections = data.get("detections", {})
            threat_meta = data.get("threat_meta", {})

            ws = streamers.get(target_cam)
            if ws:
                ws.feed_frame(jpeg_bytes, frame_id, detections)

                asyncio.create_task(
                    ws.broadcast_metadata(frame_id, detections, threat_meta)
                )

                frames_sent[target_cam] += 1
                n = frames_sent[target_cam]

                if frame_id is not None:
                    pipeline_tracker.mark_end(target_cam, frame_id)

                asyncio.create_task(
                    threat_manager.process_frame(
                        camera_id=target_cam,
                        frame_id=frame_id,
                        is_aiming=threat_meta.get("is_aiming", False),
                        has_weapon=threat_meta.get("has_weapon", False),
                        number_of_guns=threat_meta.get("number_of_guns", 0),
                        face_identities=threat_meta.get("face_identities", []),
                    )
                )

                dispatcher = dispatchers.get(target_cam)
                if dispatcher:
                    await dispatcher.add(frame_id, detections, threat_meta)

                if n % LOG_EVERY_N_FRAMES == 0:
                    print(
                        f"[stream/{target_cam}] 📺 {n} frames sent "
                        f"(frame_id={frame_id}, size={len(jpeg_bytes)} bytes)"
                    )

    except asyncio.CancelledError:
        print("[stream] 🛑 Streaming service cancelled.")
    except Exception as e:
        print(f"[stream] 🔥 Streaming service error: {e}")
    finally:
        for cam_id, ws in streamers.items():
            await ws.stop()
        _active_streams.clear()
        print("[stream] All WebRTC streamers stopped.")


async def stop_streaming(camera_ids: list):
    for cam_id in camera_ids:
        ws = _active_streams.pop(cam_id, None)
        if ws:
            await ws.stop()
        metadata_dispatcher_manager.remove(cam_id)
    print(f"[stream] 🛑 Stopped streaming for cameras: {camera_ids}")
