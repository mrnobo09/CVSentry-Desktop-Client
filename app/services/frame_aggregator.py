import asyncio
import orjson
import heapq
import time
from typing import List, Dict, Any
from utils.frame_cache import frame_cache
from utils.draw_utils import draw_detections
from concurrent.futures import ThreadPoolExecutor

THREAD_POOL = ThreadPoolExecutor(max_workers=8)


def _check_combined_threat(weapon_dets: list, face_dets: list) -> bool:
    """
    Returns True when a RECOGNIZED face is sufficiently contained
    within a person who has_weapon=True.
    """
    armed_boxes = [
        d["box"] for d in weapon_dets
        if d.get("class_name") == "person_pose" and d.get("has_weapon")
    ]
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
            
            inter_x1 = max(ax1, fx1)
            inter_y1 = max(ay1, fy1)
            inter_x2 = min(ax2, fx2)
            inter_y2 = min(ay2, fy2)
            
            if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                face_area = (fx2 - fx1) * (fy2 - fy1)
                
                # Require 80% of face box to be inside person box AND face vertically in upper half
                if face_area > 0 and (inter_area / face_area) > 0.8:
                    person_mid_y = ay1 + (ay2 - ay1) / 2
                    if fy1 < person_mid_y:
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
                inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                face_area = (fx2 - fx1) * (fy2 - fy1)
                if face_area > 0 and (inter_area / face_area) > 0.8:
                    person_mid_y = ay1 + (ay2 - ay1) / 2
                    if fy1 < person_mid_y:
                        extras.append({
                            "class_name": "COMBINED_THREAT",
                            "box": person["box"],
                            "score": 1.0,
                            "identity": face.get("identity"),
                        })
    return extras


async def frame_aggregator(redis_manager, camera_ids: list):
    """
    Aggregates weapon + face detection results, merges detections strictly by frame_id,
    draws annotations via ThreadPool, and yields frames for the RTMP broadcaster.
    """
    streams = {
        **{f"weapon:{cam_id}": "$" for cam_id in camera_ids},
        **{f"face:{cam_id}":   "$" for cam_id in camera_ids},
    }

    # Increased Jitter Buffer Size for smoother outputs from delayed multithreading
    BUFFER_SIZE = 5
    LOG_EVERY_N = 30
    frame_buffers: dict = {cam_id: [] for cam_id in camera_ids}

    fps_stats = {cam_id: {"count": 0, "start_time": time.time()} for cam_id in camera_ids}
    FPS_REPORT_INTERVAL = 10

    # Strict Frame Synchronization Caches by frame_id
    face_cache: dict = {cam_id: {} for cam_id in camera_ids}
    pending_weapons: dict = {cam_id: {} for cam_id in camera_ids}

    pulled_counts: dict = {cam_id: 0 for cam_id in camera_ids}
    yielded_counts: dict = {cam_id: 0 for cam_id in camera_ids}

    print(f"[app/aggregator] 🟢 Started for cameras: {camera_ids} | buffer={BUFFER_SIZE}")
    loop = asyncio.get_running_loop()

    while True:
        try:
            r = redis_manager.get_client()
            response = await r.xread(
                streams=streams,
                count=5,     # Process up to 5 events per stream per loop to catch up fast
                block=20     # Lower block time (20ms) to check 80ms timeouts accurately
            )

            # 1. Process new incoming messages
            if response:
                for stream_name_bytes, messages in response:
                    stream_name = stream_name_bytes.decode("utf-8")
                    parts = stream_name.split(":", 1)
                    stream_type = parts[0]
                    camera_id   = parts[1]

                    for message_id, fields in messages:
                        streams[stream_name] = message_id

                        frame_id_bytes = fields.get(b"frame_id")
                        try:
                            frame_id = int(frame_id_bytes.decode("utf-8")) if frame_id_bytes else -1
                        except (ValueError, AttributeError):
                            continue

                        det_bytes   = fields.get(b"detections")
                        detections  = orjson.loads(det_bytes) if det_bytes else []

                        if stream_type == "face":
                            # Cache explicitly by frame_id
                            face_cache[camera_id][frame_id] = detections
                            has_recognition = any(d.get("recognized") for d in detections)
                            if has_recognition:
                                names = [d.get("identity") for d in detections if d.get("recognized")]
                                print(f"[app/{camera_id}] 🔍 Face recognized in frame {frame_id}: {names}")
                            
                            # GC face cache (keep last 50 max to prevent ballooning)
                            if len(face_cache[camera_id]) > 50:
                                min_k = min(face_cache[camera_id].keys())
                                del face_cache[camera_id][min_k]

                        elif stream_type == "weapon":
                            pulled_counts[camera_id] = pulled_counts.get(camera_id, 0) + 1
                            pull_n = pulled_counts[camera_id]
                            if pull_n % LOG_EVERY_N == 0:
                                print(f"[app/{camera_id}] 📨 Pulled {pull_n} result frames from weapon stream")

                            threat_bytes = fields.get(b"has_threat")
                            has_threat   = threat_bytes.decode("utf-8") == "True" if threat_bytes else False

                            count_bytes  = fields.get(b"detections_count")
                            det_count    = int(count_bytes.decode("utf-8")) if count_bytes else 0

                            # Add to pending wait queue with current timestamp
                            pending_weapons[camera_id][frame_id] = {
                                "timestamp": time.time(),
                                "detections": detections,
                                "has_threat": has_threat,
                                "det_count": det_count,
                                "message_id": message_id.decode("utf-8")
                            }

                            if len(pending_weapons[camera_id]) > 50:
                                min_k = min(pending_weapons[camera_id].keys())
                                del pending_weapons[camera_id][min_k]

            # 2. Check pending frames for matches or timeouts
            now = time.time()
            tasks_to_draw = []

            for camera_id in camera_ids:
                f_ids = list(pending_weapons[camera_id].keys())
                for f_id in f_ids:
                    w_data = pending_weapons[camera_id][f_id]
                    
                    is_match = f_id in face_cache[camera_id]
                    is_timeout = (now - w_data["timestamp"]) >= 0.08  # 80ms strict timeout buffer
                    
                    if is_match or is_timeout:
                        if is_match:
                            face_dets = face_cache[camera_id].pop(f_id)
                        else:
                            face_dets = []

                        raw_frame_bytes = frame_cache.get(camera_id, f_id)
                        if raw_frame_bytes is None:
                            # Frame expired from in-memory pool
                            del pending_weapons[camera_id][f_id]
                            continue

                        # Add to batch draw task
                        tasks_to_draw.append({
                            "camera_id": camera_id,
                            "frame_id": f_id,
                            "w_data": w_data,
                            "face_dets": face_dets,
                            "raw_frame_bytes": raw_frame_bytes
                        })
                        
                        del pending_weapons[camera_id][f_id]

            # 3. Offload drawing in parallel
            if tasks_to_draw:
                async def process_draw_task(task_spec):
                    c_id = task_spec["camera_id"]
                    f_id = task_spec["frame_id"]
                    w_d = task_spec["w_data"]
                    f_dets = task_spec["face_dets"]
                    raw_bytes = task_spec["raw_frame_bytes"]
                    w_dets = w_d["detections"]
                    
                    has_rec = any(d.get("recognized") for d in f_dets)
                    has_comb = _check_combined_threat(w_dets, f_dets)
                    f_ids = _get_recognized_identities(f_dets)
                    
                    comb_dets = w_dets + f_dets
                    if has_comb:
                        comb_dets += _build_combined_threat_detections(w_dets, f_dets)
                        
                    if comb_dets:
                        anno_bytes = await loop.run_in_executor(
                            THREAD_POOL,
                            draw_detections,
                            raw_bytes,
                            comb_dets
                        )
                    else:
                        anno_bytes = raw_bytes
                        
                    return {
                        "camera_id": c_id,
                        "message_id": w_d["message_id"],
                        "frame_id": f_id,
                        "frame_bytes": anno_bytes,
                        "detections": comb_dets,
                        "detections_count": w_d["det_count"] + len(f_dets),
                        "has_threat": w_d["has_threat"],
                        "has_recognition": has_rec,
                        "has_combined_threat": has_comb,
                        "face_identities": f_ids,
                    }

                # Executing drawing concurrently over the thread pool
                drawn_results = await asyncio.gather(*(process_draw_task(t) for t in tasks_to_draw))

                for frame_data in drawn_results:
                    c_id = frame_data["camera_id"]
                    heapq.heappush(frame_buffers[c_id], (frame_data["frame_id"], frame_data))

                    if len(frame_buffers[c_id]) > BUFFER_SIZE:
                        _, sorted_frame = heapq.heappop(frame_buffers[c_id])

                        yielded_counts[c_id] = yielded_counts.get(c_id, 0) + 1
                        yield_n = yielded_counts[c_id]

                        if sorted_frame.get("has_combined_threat"):
                            ids = sorted_frame.get("face_identities", [])
                            print(f"[app/{c_id}] 🚨🔍 COMBINED THREAT | frame={sorted_frame['frame_id']} | identities={ids}")
                        elif sorted_frame.get("has_threat"):
                            print(f"[app/{c_id}] 🚨 THREAT frame → SRS | frame_id={sorted_frame['frame_id']}")
                        elif yield_n % LOG_EVERY_N == 0:
                            print(f"[app/{c_id}] 🖼️  Yielded {yield_n} annotated frames to RTMP broadcaster")

                        yield sorted_frame

                        # FPS Stats
                        stats = fps_stats[c_id]
                        stats["count"] += 1
                        if stats["count"] >= FPS_REPORT_INTERVAL:
                            elapsed = time.time() - stats["start_time"]
                            if elapsed > 0:
                                print(f"📊 [{c_id}] Output FPS: {stats['count'] / elapsed:.2f}")
                            stats["count"] = 0
                            stats["start_time"] = time.time()

            # Small sleep purely to yield execution if completely idle
            if not response and not tasks_to_draw:
                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            print("[app/aggregator] Aggregator task cancelled.")
            break
        except Exception as e:
            print(f"⚠️ [app/aggregator] Error: {e}")
            await asyncio.sleep(1)