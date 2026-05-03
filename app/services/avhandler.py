import av
import asyncio
import threading
import queue
import io
from typing import Dict, Optional
from av.video.reformatter import VideoReformatter
from turbojpeg import TurboJPEG

jpeg = TurboJPEG()


# Parameters to tune performance
FRAME_SKIP = 3          # Keep 1 in every N frames  (higher = fewer frames, less CPU/Redis load)
JPEG_QUALITY = 60       # JPEG encode quality (50-75 is a good range)
INFER_RESOLUTION = 640  # Long-edge cap before pushing to Redis (matches YOLO training size)


class AVHandler:
    def __init__(self):
        self.containers: Dict[str, av.container.InputContainer] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.frame_queues: Dict[str, queue.Queue[bytes]] = {}
        self.running: Dict[str, bool] = {}
        self.lock = asyncio.Lock()

    async def start_pipeline(self, camera_id: str, rtsp_url: str):
        """Starts a new video pipeline in a background thread."""
        async with self.lock:
            if camera_id in self.containers:
                raise ValueError(f"Pipeline for camera_id {camera_id} already exists.")

            try:
                container = av.open(
                    rtsp_url,
                    options={
                        'rtsp_transport': 'tcp',
                        'max_delay': '5000',
                        'fflags': 'nobuffer',
                        'flags': 'low_delay',
                        'probesize': '32',
                        'analyzeduration': '0',
                        'strict': 'experimental'
                    },
                    timeout=10.0
                )

                self.containers[camera_id] = container
                self.frame_queues[camera_id] = queue.Queue(maxsize=2)
                self.running[camera_id] = True

                thread = threading.Thread(
                    target=self._decode_loop,
                    args=(camera_id,),
                    daemon=True,
                    name=f"AVHandler-{camera_id}"
                )
                thread.start()
                self.threads[camera_id] = thread

                print(f"✓ Started pipeline for {camera_id}")

            except Exception as e:
                print(f"✗ Failed to start pipeline for {camera_id}: {e}")
                self.containers.pop(camera_id, None)
                self.frame_queues.pop(camera_id, None)
                self.running[camera_id] = False
                raise

    def _decode_loop(self, camera_id: str):
        """Decode loop running in the background thread."""
        try:
            container = self.containers[camera_id]
            frame_queue = self.frame_queues[camera_id]
        except KeyError:
            print(f"Decode loop for {camera_id} stopping: resources not found.")
            return

        print(f"Decode loop started for {camera_id}...")

        frame_counter = 0

        try:
            for packet in container.demux(video=0):
                if not self.running.get(camera_id, False):
                    break

                if packet.stream.type != 'video':
                    continue

                for frame in packet.decode():
                    frame_counter += 1

                    # Frame Skipping
                    if frame_counter % FRAME_SKIP != 0:
                        continue  

                    # Downscale to 640x480 and convert to BGR24 using PyAV Reformatter
                    if not hasattr(self, 'reformatters'):
                        self.reformatters = {}
                    if camera_id not in self.reformatters:
                        self.reformatters[camera_id] = VideoReformatter()
                    
                    frame_bgr = self.reformatters[camera_id].reformat(frame, width=640, height=480, format='bgr24')
                    
                    # Convert to numpy array
                    img_array = frame_bgr.to_ndarray(format='bgr24')

                    # JPEG Encoding with PyTurboJPEG
                    img_bytes = jpeg.encode(img_array, quality=JPEG_QUALITY)



                    # Keep queue fresh
                    if frame_queue.full():
                        try:
                            frame_queue.get_nowait()
                        except queue.Empty:
                            pass

                    frame_queue.put(img_bytes)

        except Exception as e:
            if "End of file" in str(e) or "Input/output error" in str(e):
                print(f"Stream ended or disconnected for {camera_id}.")
            else:
                print(f"Decode error for {camera_id}: {e}")

        finally:
            print(f"Decode loop ended for {camera_id}")
            self.running[camera_id] = False

    def get_frame(self, camera_id: str) -> Optional[bytes]:
        """Return latest frame or None."""
        if camera_id not in self.frame_queues:
            return None

        try:
            return self.frame_queues[camera_id].get_nowait()
        except queue.Empty:
            return None

    async def stop_pipeline(self, camera_id: str):
        """Stops a running pipeline and cleans up resources."""
        async with self.lock:
            if camera_id not in self.containers:
                print(f"Pipeline for {camera_id} not found (already stopped?).")
                return

            print(f"Stopping pipeline for {camera_id}...")
            self.running[camera_id] = False

            # Stop thread
            if camera_id in self.threads:
                self.threads[camera_id].join(timeout=2)
                self.threads.pop(camera_id, None)

            # Close stream
            try:
                self.containers[camera_id].close()
            except Exception as e:
                print(f"Error closing container for {camera_id}: {e}")

            self.containers.pop(camera_id, None)

            # Clear frames
            if camera_id in self.frame_queues:
                q = self.frame_queues[camera_id]
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
                self.frame_queues.pop(camera_id, None)

            self.running.pop(camera_id, None)

            print(f"Stopped pipeline for {camera_id}")
