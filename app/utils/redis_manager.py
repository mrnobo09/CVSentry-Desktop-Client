import redis
import os
from typing import Optional, List, Any

class RedisManager:

    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379)) 
    MAX_FRAMES_PER_CYCLE = 100000
    
    STREAM_MAXLEN = 1000 

    GROUPS = {
        "faces": "face_group",
        "weapons": "weapon_group",
    }

    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.pool: Optional[redis.ConnectionPool] = None

    def get_client(self) -> redis.Redis:
        if self.client is None:
            if self.pool is None:
                self.pool = redis.ConnectionPool(
                    host=self.REDIS_HOST, 
                    port=self.REDIS_PORT, 
                    decode_responses=False, # Crucial for images (binary data)
                    max_connections=50      
                )
            self.client = redis.Redis(connection_pool=self.pool)
        
        return self.client
    
    def get_frame_id(self, camera_id: str) -> int:
        r = self.get_client()
        counter_key = f'counter:{camera_id}:frame_id'
        current_id = r.incr(counter_key)

        if current_id > self.MAX_FRAMES_PER_CYCLE:
            r.set(counter_key, 1)
            current_id = 1

        return current_id
    
    def stream_frame(self, camera_id: str, frame_id:int, frame_data: bytes):
        """
        Push a frame to the Main Stream AND fan-out to all Consumer Group streams.
        """
        r = self.get_client()
        
        # Prepare the data payload once
        payload = {
            'frame_id': str(frame_id),
            'frame_data': frame_data,
        }
        
        # Key: stream:cam_01
        main_stream_key = f'stream:{camera_id}'

        # Keys: stream:cam_01:face_group, stream:cam_01:weapon_group, etc.
        for task_name, group_suffix in self.GROUPS.items():
            group_stream_key = f'{main_stream_key}:{group_suffix}'
            r.xadd(
                group_stream_key,
                payload,
                maxlen=self.STREAM_MAXLEN,
                approximate=True
            )
            

    def fetch_frames(self, camera_id: str, last_id: str = '$', count: int = 1, block: int = 1000) -> list:
        """
        Fetch new processed frames from the stream.
        """
        r = self.get_client()
        stream_key = f'processed:{camera_id}'

        try:
            response = r.xread(
                streams={stream_key: last_id},
                count=count,
                block=block
            )
            return response
        except redis.RedisError as e:
            print(f"Error fetching from {stream_key}: {e}")
            return []

redis_manager = RedisManager()