import cv2
import numpy as np
import redis
import threading
import queue
import asyncio

from services.analysis import FrameAnalyzer

analyzer = FrameAnalyzer(skip_frames=0)

# -----------------------------
# Configuration
# -----------------------------
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
CAMERAS = ["cam_1"]

# -----------------------------
# Redis connection
# -----------------------------
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# -----------------------------
# Queues for frames
# -----------------------------
frame_queues = {cam: queue.Queue(maxsize=1) for cam in CAMERAS}

# -----------------------------
# Frame fetching function
# -----------------------------
def fetch_frames(camera_id):
    stream_key = f"stream:{camera_id}"
    last_id = "$"  # Start from new frames only. Use "0-0" to read all
    print(f"[{camera_id}] Listening to Redis stream: {stream_key}")

    while True:
        msgs = r.xread({stream_key: last_id}, block=1000, count=1)
        if not msgs:
            continue

        _, entries = msgs[0]
        for msg_id, fields in entries:
            last_id = msg_id
            frame_bytes = fields.get(b'frame_data')
            if frame_bytes is None:
                continue

            np_arr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is not None:
                if frame_queues[camera_id].full():
                    try:
                        frame_queues[camera_id].get_nowait()
                    except queue.Empty:
                        pass
                frame_queues[camera_id].put(frame)

# -----------------------------
# Main function
# -----------------------------
async def main():
    # Start fetching threads
    for cam in CAMERAS:
        t = threading.Thread(target=fetch_frames, args=(cam,), daemon=True)
        t.start()

    # Main display loop
    try:
        while True:
            for cam in CAMERAS:
                if not frame_queues[cam].empty():
                    frame = frame_queues[cam].get()
                    analyzed_frame, detections = await analyzer.analyze_frame(frame)
                    if analyzed_frame is not None:
                        cv2.imshow(cam, analyzed_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Exiting viewer...")
                break

            await asyncio.sleep(0.001)

    finally:
        cv2.destroyAllWindows()
        print("Viewer closed.")

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())
