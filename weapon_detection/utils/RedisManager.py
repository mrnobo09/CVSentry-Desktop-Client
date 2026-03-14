import redis.asyncio as redis
from typing import Optional, List

import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# Redis Configuration
# -----------------------------
REDIS_CONF = {
    "host": os.environ.get("REDIS_HOST", "127.0.0.1"),
    "port": int(os.environ.get("REDIS_PORT", 6379)),
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

    # --- EXISTING METHODS ---

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

    # --- NEW CONSUMER GROUP METHODS ---

    async def ensure_group(self, stream_key: str, group_name: str):
        """Creates the consumer group if it does not exist."""
        if not self.client: return
        try:
            # id="0" means create group pointing to the start of stream. 
            # mkstream=True creates the stream if it doesn't exist yet.
            await self.client.xgroup_create(stream_key, group_name, id="0", mkstream=True)
        except redis.ResponseError as e:
            # "BUSYGROUP Consumer Group name already exists" is expected
            if "BUSYGROUP" not in str(e):
                print(f"⚠️ Error creating group {group_name}: {e}")

    async def read_group_stream(self, stream_key: str, group_name: str, consumer_name: str, count: int = 1, block: int = 1000) -> List:
        """Reads from a consumer group using XREADGROUP."""
        if not self.client: return []
        try:
            # '>' means "give me messages never delivered to any other consumer"
            return await self.client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream_key: ">"},
                count=count,
                block=block
            )
        except Exception as e:
            print(f"❌ Read Group Error: {e}")
            return []

    async def ack_message(self, stream_key: str, group_name: str, msg_ids: List[str]):
        """Acknowledges processed messages."""
        if not self.client: return
        if not msg_ids: return
        await self.client.xack(stream_key, group_name, *msg_ids)

redis_manager = RedisManager.get_instance()