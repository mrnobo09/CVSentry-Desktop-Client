import asyncio
from services.avhandler import AVHandler
from schemas.cameras import Cameras
from utils.redis_manager import redis_manager as rdb
from utils.frame_cache import frame_cache
from utils.latency_tracker import pipeline_tracker
from routes.node_routes import notify_cameras_active

# Log every Nth frame to avoid console flood
LOG_EVERY_N_FRAMES = 30


global_av_handler = AVHandler()

async def AnalyzeCameraStreams(cameras: Cameras):
    """Analyze camera streams asynchronously."""
    global global_av_handler
    for camera_id, camera_info in cameras.items():
        rtsp_url = camera_info.rtsp_url
        print(f"[app/{camera_id}] 🎬 Starting RTSP ingestion from {rtsp_url}")
        asyncio.create_task(CameraWorker(camera_id, rtsp_url, global_av_handler))


async def CameraWorker(camera_id: str, rtsp_url: str, avhandler: AVHandler):
    """Worker to handle individual camera stream analysis."""
    try:
        await avhandler.start_pipeline(camera_id, rtsp_url)

        frames_pushed = 0
        first_frame_notified = False  # Only notify Django once per camera

        while avhandler.running.get(camera_id, False):
            frame = avhandler.get_frame(camera_id)
            if frame is not None:
                frame_id = await rdb.get_frame_id(camera_id)
                pipeline_tracker.mark_start(camera_id, frame_id)
                frame_cache.add(camera_id, frame_id, frame)
                await rdb.stream_frame(camera_id, frame_id, frame)

                frames_pushed += 1

                # Trigger 2: notify Django the moment the first real frame arrives
                if not first_frame_notified:
                    first_frame_notified = True
                    print(f"[app/{camera_id}] 🖼️  First frame received — notifying Django node is live")
                    active_cams = [cid for cid, is_running in avhandler.running.items() if is_running]
                    asyncio.create_task(
                        notify_cameras_active(active_cams, reason="first frame live")
                    )

                if frames_pushed % LOG_EVERY_N_FRAMES == 0:
                    print(
                        f"[app/{camera_id}] 📤 Pushed {frames_pushed} frames to Redis "
                        f"(latest frame_id={frame_id}, size={len(frame)} bytes)"
                    )

            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        print(f"[app/{camera_id}] 🛑 CameraWorker task cancelled")
    except Exception as e:
        print(f"[app/{camera_id}] ❌ Pipeline failed: {e}")

    finally:
        if camera_id in avhandler.containers:
            await avhandler.stop_pipeline(camera_id)
            print(f"[app/{camera_id}] 🛑 Pipeline stopped")