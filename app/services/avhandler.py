import av
import asyncio
import threading
import queue
import io  # Added for in-memory byte buffer
from typing import Dict, Optional
import numpy as np

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
                # Open the RTSP stream
                container = av.open(
                    rtsp_url,
                    options={
                        'rtsp_transport': 'tcp',  # Using TCP for stability
                        'max_delay': '100',    # Increase buffer time
                        'fflags': 'nobuffer',     # Reduce latency
                        'flags': 'low_delay',     # Reduce latency
                        'strict': 'experimental'
                    },
                    timeout=10.0  # Connection timeout
                )
                
                self.containers[camera_id] = container
                # Set maxsize to 2 to keep only the latest frames
                self.frame_queues[camera_id] = queue.Queue(maxsize=2)
                self.running[camera_id] = True
                
                # Start the background thread for decoding
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
                # Clean up if setup failed
                if camera_id in self.containers:
                    del self.containers[camera_id]
                if camera_id in self.frame_queues:
                    del self.frame_queues[camera_id]
                self.running[camera_id] = False
                raise
    
    def _decode_loop(self, camera_id: str):
        """
        Background thread target.
        Demuxes, decodes, and re-encodes frames as JPEG bytes.
        """
        try:
            container = self.containers[camera_id]
            frame_queue = self.frame_queues[camera_id]
        except KeyError:
            print(f"Decode loop for {camera_id} stopping: resources not found.")
            return

        print(f"Decode loop started for {camera_id}...")
        
        try:
            for packet in container.demux(video=0):
                if not self.running.get(camera_id, False):
                    break
                
                if packet.stream.type == 'video':
                    for frame in packet.decode():
                        #JPEG Encoding
                        pil_img = frame.to_image()
                        
                        with io.BytesIO() as buffer:
                            pil_img.save(buffer, format='jpeg', quality=85)
                            img_bytes = buffer.getvalue()

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
        """
        Get the latest frame from the queue (non-blocking).
        Returns:
            Optional[bytes]: JPEG-encoded frame as bytes, or None if queue is empty.
        """
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
            
            if camera_id in self.threads:
                self.threads[camera_id].join(timeout=2.0)
                if self.threads[camera_id].is_alive():
                    print(f"Warning: Decode thread for {camera_id} did not exit gracefully.")
                del self.threads[camera_id]
            
            # Close and release the container
            if camera_id in self.containers:
                try:
                    self.containers[camera_id].close()
                except Exception as e:
                    print(f"Error closing container for {camera_id}: {e}")
                del self.containers[camera_id]
            
            # Clear the queue
            if camera_id in self.frame_queues:
                # Clear remaining items
                while not self.frame_queues[camera_id].empty():
                    try:
                        self.frame_queues[camera_id].get_nowait()
                    except queue.Empty:
                        break
                del self.frame_queues[camera_id]
            
            # Remove the running state entry
            if camera_id in self.running:
                del self.running[camera_id]
            
            print(f"Stopped pipeline for {camera_id}")