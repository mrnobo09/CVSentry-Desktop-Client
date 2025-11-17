import redis.asyncio as redis
from typing import Optional, List

# -----------------------------
# Redis Configuration
# -----------------------------
REDIS_CONF = {
    "host": "127.0.0.1",
    "port": 6379,
    "decode_responses": False 
}

class RedisManager:
    _instance: Optional["RedisManager"] = None

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    @classmethod
    def get_instance(cls) -> "RedisManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self):
        """Initializes connection using internal configuration."""
        if self.client is None:
            try:
                self.client = redis.Redis(**REDIS_CONF)
                await self.client.ping()
                print(f"✅ RedisManager: Connected to {REDIS_CONF['host']}:{REDIS_CONF['port']}")
            except Exception as e:
                print(f"❌ RedisManager: Connection failed - {e}")
                raise e

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None
            print("zz RedisManager: Connection closed")

    def get_client(self) -> redis.Redis:
        if self.client is None:
            raise ConnectionError("Redis client not initialized.")
        return self.client


    async def read_stream(self, stream_key: str, last_id: str = "$", block: int = 1000) -> List:
        if not self.client: return []
        return await self.client.xread(streams={stream_key: last_id}, block=block, count=1)

    async def push_frame(self, stream_key: str, frame_bytes: bytes, metadata: dict = None):
        if not self.client: return
        
        data = {"frame_data": frame_bytes}
        if metadata:
            for k, v in metadata.items():
                data[k] = str(v)

        await self.client.xadd(stream_key, data)

redis_manager = RedisManager.get_instance()