import asyncio
import base64
import json
import redis
import numpy as np
import cv2
from typing import Dict, Set, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FrameAggregator:
    """
    Aggregates frames from Redis streams and converts them to base64
    for WebSocket transmission to frontend clients.
    """
    
    def __init__(self, redis_host: str = "127.0.0.1", redis_port: int = 6379):
        """
        Initialize the Frame Aggregator.
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=False)
        
        # Track active camera streams
        self.active_cameras: Set[str] = set()
        
        # Store last processed message IDs for each camera
        self.last_ids: Dict[str, str] = {}
        
        self.websocket_handlers: Dict[str, callable] = {}
        
        logger.info(f"FrameAggregator initialized with Redis at {redis_host}:{redis_port}")
    
    def add_camera(self, cam_id: str, websocket_handler: Optional[callable] = None):
        """
        Add a camera to the aggregator.
        
        Args:
            cam_id: Camera identifier (e.g., "cam_1", "cam_2")
            websocket_handler: Optional async function to handle sending frames via WebSocket
        """
        self.active_cameras.add(cam_id)
        self.last_ids[cam_id] = "$"  # Start from new messages
        
        if websocket_handler:
            self.websocket_handlers[cam_id] = websocket_handler
        
        logger.info(f"Added camera: {cam_id}")
    
    def remove_camera(self, cam_id: str):
        """
        Remove a camera from the aggregator.
        
        Args:
            cam_id: Camera identifier
        """
        self.active_cameras.discard(cam_id)
        self.last_ids.pop(cam_id, None)
        self.websocket_handlers.pop(cam_id, None)
        
        logger.info(f"Removed camera: {cam_id}")
    
    def frame_to_base64(self, frame_bytes: bytes) -> Optional[str]:
        """
        Convert frame bytes to base64 encoded JPEG string.
        """
        try:
            
            return base64.b64encode(frame_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error converting frame to base64: {e}")
            return None
    
    async def process_camera_stream(self, cam_id: str):
        """
        Process frames from a single camera's Redis stream.
        
        Args:
            cam_id: Camera identifier
        """
        stream_key = f"processed:{cam_id}"
        logger.info(f"[{cam_id}] Starting to process stream: {stream_key}")
        
        while cam_id in self.active_cameras:
            try:
                # Read from Redis stream
                messages = self.redis_client.xread(
                    {stream_key: self.last_ids[cam_id]},
                    block=1000,  # Block for 1 second
                    count=1
                )
                
                if not messages:
                    await asyncio.sleep(0.01)  # Small delay to prevent tight loop
                    continue
                
                # Process each message
                _, entries = messages[0]
                for msg_id, fields in entries:
                    # Update last processed ID
                    self.last_ids[cam_id] = msg_id
                    
                    # Get frame data
                    frame_bytes = fields.get(b'frame_data')
                    if frame_bytes is None:
                        continue
                    
                    # Convert to base64
                    frame_base64 = self.frame_to_base64(frame_bytes)
                    if frame_base64 is None:
                        continue
                    
                    # Prepare payload for WebSocket
                    payload = {
                        "cam_id": cam_id,
                        "frame": frame_base64,
                        "timestamp": msg_id.decode('utf-8') if isinstance(msg_id, bytes) else msg_id
                    }
                    
                    # Send via WebSocket if handler exists
                    if cam_id in self.websocket_handlers:
                        handler = self.websocket_handlers[cam_id]
                        await handler(payload)
                    else:
                        # Log if no handler (for debugging)
                        logger.debug(f"[{cam_id}] Frame processed but no WebSocket handler")
                
            except redis.RedisError as e:
                logger.error(f"[{cam_id}] Redis error: {e}")
                await asyncio.sleep(1)  # Wait before retrying
                
            except Exception as e:
                logger.error(f"[{cam_id}] Unexpected error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"[{cam_id}] Stopped processing stream")
    
    async def start(self):
        """
        Start processing all active camera streams.
        Creates an async task for each camera.
        """
        logger.info(f"Starting aggregator for {len(self.active_cameras)} cameras")
        
        tasks = []
        for cam_id in self.active_cameras:
            task = asyncio.create_task(self.process_camera_stream(cam_id))
            tasks.append(task)
        
        # Wait for all tasks
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """
        Stop processing all camera streams.
        """
        logger.info("Stopping aggregator")
        self.active_cameras.clear()
        self.websocket_handlers.clear()