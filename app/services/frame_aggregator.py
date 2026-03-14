import asyncio
import json
import heapq
import time
from typing import List, Dict, Any
from utils.frame_cache import frame_cache
from utils.draw_utils import draw_detections
from concurrent.futures import ProcessPoolExecutor

PROCESS_POOL = ProcessPoolExecutor(max_workers=4)


def _check_combined_threat(weapon_dets: list, face_dets: list) -> bool:
    """
    Returns True when a RECOGNIZED face spatially overlaps with a
    person who has_weapon=True.

    Uses simple box-overlap (IoU > 0 is enough — any overlap counts).
    """
    # Collect armed person boxes
    armed_boxes = [
        d["box"] for d in weapon_dets
        if d.get("class_name") == "person_pose" and d.get("has_weapon")
    ]
    # Collect recognized face boxes
    recognized_face_boxes = [
        (d["box"], d.get("identity"))
        for d in face_dets
        if d.get("recognized") and d.get("box")
    ]

    if not armed_boxes or not recognized_face_boxes:
        return False

    for armed_box in armed_boxes:
        ax1, ay1, ax2, ay2 = armed_box
        for face_box, _ in recognized_face_boxes:
            fx1, fy1, fx2, fy2 = face_box
            # Check any overlap
            inter_x1 = max(ax1, fx1)
            inter_y1 = max(ay1, fy1)
            inter_x2 = min(ax2, fx2)
            inter_y2 = min(ay2, fy2)
            if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                return True
    return False


def _get_recognized_identities(face_dets: list) -> list:
    """Returns all recognized identity names from face detections."""
    return [
        d.get("identity")
        for d in face_dets
        if d.get("recognized") and d.get("identity")
    ]


def _build_combined_threat_detections(weapon_dets: list, face_dets: list) -> list:
    """
    Injects COMBINED_THREAT entries for the draw layer when a recognized
    face overlaps with an armed person.
    """
    extras = []
    armed_people = [
        d for d in weapon_dets
        if d.get("class_name") == "person_pose" and d.get("has_weapon")
    ]
    recognized_faces = [
        d for d in face_dets
        if d.get("recognized") and d.get("box")
    ]

    for person in armed_people:
        ax1, ay1, ax2, ay2 = person["box"]
        for face in recognized_faces:
            fx1, fy1, fx2, fy2 = face["box"]
            inter_x1 = max(ax1, fx1)
            inter_y1 = max(ay1, fy1)
            inter_x2 = min(ax2, fx2)
            inter_y2 = min(ay2, fy2)
            if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                extras.append({
                    "class_name": "COMBINED_THREAT",
                    "box": person["box"],
                    "score": 1.0,
                    "identity": face.get("identity"),
                })
    return extras


async def frame_aggregator(redis_manager, camera_ids: list):
    """
    Aggregates weapon + face detection results, merges detections,
    draws annotations, and yields frames for the RTMP broadcaster.

    Reads from:
      - weapon:{cam_id}  (weapon detection results)
      - face:{cam_id}    (face detection results)

    Yields frame_data dict with:
      - has_threat          bool  (weapon threat)
      - has_recognition     bool  (face recognized)
      - has_combined_threat bool  (recognized face + armed person overlap)
      - face_identities     list  (recognized names in frame)
    """
    # Multi-stream read: weapon + face for every camera
    streams = {
        **{f"weapon:{cam_id}": "$" for cam_id in camera_ids},
        **{f"face:{cam_id}":   "$" for cam_id in camera_ids},
    }

    BUFFER_SIZE = 2
    LOG_EVERY_N = 30
    frame_buffers: dict = {cam_id: [] for cam_id in camera_ids}

    fps_stats = {cam_id: {"count": 0, "start_time": time.time()} for cam_id in camera_ids}
    FPS_REPORT_INTERVAL = 10

    # Per-camera latest face results cache (face results arrive independently)
    face_cache: dict = {cam_id: [] for cam_id in camera_ids}

    # Per-camera counters
    pulled_counts: dict = {cam_id: 0 for cam_id in camera_ids}
    yielded_counts: dict = {cam_id: 0 for cam_id in camera_ids}

    print(f"[app/aggregator] 🟢 Started for cameras: {camera_ids} | buffer={BUFFER_SIZE}")
    loop = asyncio.get_running_loop()

    while True:
        try:
            r = redis_manager.get_client()
            response = await asyncio.to_thread(
                r.xread,
                streams=streams,
                count=1,
                block=100
            )

            if not response:
                await asyncio.sleep(0.001)
                continue

            for stream_name_bytes, messages in response:
                stream_name = stream_name_bytes.decode("utf-8")
                # e.g. "weapon:cam_01" or "face:cam_01"
                parts = stream_name.split(":", 1)
                stream_type = parts[0]          # "weapon" or "face"
                camera_id   = parts[1]          # "cam_01"

                for message_id, fields in messages:
                    streams[stream_name] = message_id

                    frame_id_bytes = fields.get(b"frame_id")
                    try:
                        frame_id = int(frame_id_bytes.decode("utf-8")) if frame_id_bytes else -1
                    except (ValueError, AttributeError):
                        continue

                    det_bytes   = fields.get(b"detections")
                    detections  = json.loads(det_bytes.decode("utf-8")) if det_bytes else []

                    # ---- FACE STREAM: just cache the latest results ----
                    if stream_type == "face":
                        face_cache[camera_id] = detections
                        has_recognition = any(d.get("recognized") for d in detections)
                        if has_recognition:
                            names = [d.get("identity") for d in detections if d.get("recognized")]
                            print(f"[app/{camera_id}] 🔍 Face recognized in frame {frame_id}: {names}")
                        continue  # face results alone don't trigger a frame yield

                    # ---- WEAPON STREAM: main render/yield path ----
                    pulled_counts[camera_id] = pulled_counts.get(camera_id, 0) + 1
                    pull_n = pulled_counts[camera_id]
                    if pull_n % LOG_EVERY_N == 0:
                        print(f"[app/{camera_id}] 📨 Pulled {pull_n} result frames from weapon stream")

                    threat_bytes = fields.get(b"has_threat")
                    has_threat   = threat_bytes.decode("utf-8") == "True" if threat_bytes else False

                    count_bytes  = fields.get(b"detections_count")
                    det_count    = int(count_bytes.decode("utf-8")) if count_bytes else 0

                    # Fetch original frame from in-memory cache
                    raw_frame_bytes = frame_cache.get(camera_id, frame_id)
                    if raw_frame_bytes is None:
                        continue

                    # Merge weapon + face detections for this frame
                    face_dets   = face_cache.get(camera_id, [])
                    has_recognition   = any(d.get("recognized") for d in face_dets)
                    has_combined_threat = _check_combined_threat(detections, face_dets)
                    face_identities   = _get_recognized_identities(face_dets)

                    # Build combined detection list for drawing
                    combined_dets = detections + face_dets
                    if has_combined_threat:
                        combined_dets += _build_combined_threat_detections(detections, face_dets)

                    # Draw (offloaded to process pool)
                    if combined_dets:
                        annotated_frame_bytes = await loop.run_in_executor(
                            PROCESS_POOL,
                            draw_detections,
                            raw_frame_bytes,
                            combined_dets
                        )
                    else:
                        annotated_frame_bytes = raw_frame_bytes

                    # Build result
                    frame_data = {
                        "camera_id":          camera_id,
                        "message_id":         message_id.decode("utf-8"),
                        "frame_id":           frame_id,
                        "frame_bytes":        annotated_frame_bytes,
                        "detections":         combined_dets,
                        "detections_count":   det_count + len(face_dets),
                        "has_threat":         has_threat,
                        "has_recognition":    has_recognition,
                        "has_combined_threat": has_combined_threat,
                        "face_identities":    face_identities,
                    }

                    # Sort & Yield
                    if camera_id in frame_buffers:
                        heapq.heappush(frame_buffers[camera_id], (frame_id, frame_data))

                        if len(frame_buffers[camera_id]) > BUFFER_SIZE:
                            _, sorted_frame = heapq.heappop(frame_buffers[camera_id])

                            yielded_counts[camera_id] = yielded_counts.get(camera_id, 0) + 1
                            yield_n = yielded_counts[camera_id]

                            if sorted_frame.get("has_combined_threat"):
                                ids = sorted_frame.get("face_identities", [])
                                print(f"[app/{camera_id}] 🚨🔍 COMBINED THREAT | frame={sorted_frame['frame_id']} | identities={ids}")
                            elif sorted_frame.get("has_threat"):
                                print(f"[app/{camera_id}] 🚨 THREAT frame → SRS | frame_id={sorted_frame['frame_id']}")
                            elif yield_n % LOG_EVERY_N == 0:
                                print(f"[app/{camera_id}] 🖼️  Yielded {yield_n} annotated frames to RTMP broadcaster")

                            yield sorted_frame

                            # FPS stats
                            stats = fps_stats[camera_id]
                            stats["count"] += 1
                            if stats["count"] >= FPS_REPORT_INTERVAL:
                                elapsed = time.time() - stats["start_time"]
                                print(f"📊 [{camera_id}] Output FPS: {stats['count'] / elapsed:.2f}")
                                stats["count"] = 0
                                stats["start_time"] = time.time()

        except asyncio.CancelledError:
            print("[app/aggregator] Aggregator task cancelled.")
            break
        except Exception as e:
            print(f"⚠️ [app/aggregator] Error: {e}")
            await asyncio.sleep(1)