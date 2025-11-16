import redis
from typing import Optional


class RedisManager:

    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379 
    MAX_FRAMES_PER_CYCLE = 100000

    def __init__(self):
        self.client : Optional[redis.Redis] = None

    def get_client(self) -> redis.Redis:
        if self.client is None:
            self.client = redis.Redis(host=self.REDIS_HOST, port=self.REDIS_PORT,decode_responses=True)
        
        try:
            self.client.ping()
            print("Connected to Redis server successfully.")
        except redis.ConnectionError as e:
            print(f"Failed to connect to Redis server: {e}")
            raise

        return self.client
    
    def get_frame_id(self,camera_id:str) -> int:

        r = self.get_client()
        counter_key = f'counter:{camera_id}:frame_id'

        current_id = r.incr(counter_key)

        if current_id > self.MAX_FRAMES_PER_CYCLE:
            r.set(counter_key, 1)
            current_id = 1

        return current_id
    
    def stream_frame(self,camera_id:str,frame_id:int,frame_data):

        r = self.get_client()
        frame_id = self.get_frame_id(camera_id)
        
        stream_key = f'stream:{camera_id}'
        print(f"Streaming frame {frame_id} to {stream_key}")

        r.xadd(
            stream_key,
            {
                'frame_id': frame_id,
                'frame_data':frame_data,
            }
        )
    

redis_manager = RedisManager()

    
