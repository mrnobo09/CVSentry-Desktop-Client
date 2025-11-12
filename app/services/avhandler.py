import av
import asyncio
import threading
import queue
from typing import Dict, Optional
import numpy as np

class AVHandler:
    def __init__(self):
        self.containers: Dict[str, av.container.InputContainer] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.frame_queues: Dict[str, queue.Queue] = {}
        self.running: Dict[str, bool] = {}
        self.lock = asyncio.Lock()
    
    async def start_pipeline(self, camera_id: str, rtsp_url: str):
        async with self.lock:
            if camera_id in self.containers:
                raise ValueError(f"Pipeline for camera_id {camera_id} already exists.")
            
            try:
                container = av.open(
                    rtsp_url,
                    options={
                        'rtsp_transport': 'tcp',
                        'max_delay': '500000',
                        'fflags': 'nobuffer',
                        'flags': 'low_delay',
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
                raise
    
    def _decode_loop(self, camera_id: str):
        """Background thread to decode frames"""
        container = self.containers[camera_id]
        frame_queue = self.frame_queues[camera_id]
        
        try:
            for packet in container.demux():
                if not self.running.get(camera_id, False):
                    break
                
                if packet.stream.type == 'video':
                    for frame in packet.decode():
                        img = frame.to_ndarray(format='bgr24')
                        
                        # Drop old frames if queue is full
                        if frame_queue.full():
                            try:
                                frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        
                        frame_queue.put(img)
        except Exception as e:
            print(f"Decode error for {camera_id}: {e}")
        finally:
            print(f"Decode loop ended for {camera_id}")
    
    def get_frame(self, camera_id: str) -> Optional[np.ndarray]:
        """Get latest frame (non-blocking)"""
        if camera_id not in self.frame_queues:
            raise ValueError(f"No pipeline found for camera_id {camera_id}.")
        
        try:
            return self.frame_queues[camera_id].get_nowait()
        except queue.Empty:
            return None
    
    async def stop_pipeline(self, camera_id: str):
        async with self.lock:
            if camera_id not in self.containers:
                raise ValueError(f"No pipeline found for camera_id {camera_id}.")
            
            self.running[camera_id] = False
            
            if camera_id in self.threads:
                self.threads[camera_id].join(timeout=2.0)
                del self.threads[camera_id]
            
            if camera_id in self.containers:
                try:
                    self.containers[camera_id].close()
                except:
                    pass
                del self.containers[camera_id]
            
            if camera_id in self.frame_queues:
                del self.frame_queues[camera_id]
            
            print(f"✓ Stopped pipeline for {camera_id}")