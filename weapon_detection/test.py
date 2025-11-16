import cv2
import numpy as np
import redis
import threading
import queue

# -----------------------------
# Configuration
# -----------------------------
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
CAMERAS = ["cam_1", "cam_2"]  # Add more camera IDs if needed

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
def main():
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
                    cv2.imshow(cam, frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Exiting viewer...")
                break

    finally:
        cv2.destroyAllWindows()
        print("Viewer closed.")

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    main()
