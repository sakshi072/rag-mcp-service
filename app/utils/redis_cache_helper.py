
import json
import redis.asyncio as redis
import logging
from app.schemas import SearchResult
from app.core.settings import settings

logger = logging.getLogger(__name__)

REDIS_HOST = settings.redis.redis_host
REDIS_PORT = settings.redis.redis_port

# Initialize Redis
redis_client = redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
# redis_client = redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_response)

class SearchCache:
    """Redis cache for frequent search query results"""

    @classmethod
    async def get(cls, search_id:str):
        try:
            data = await redis_client.get(search_id)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Redis GET failed: {e}. Falling back to DB")
            return None
    
    @classmethod
    async def set(cls, search_id:str, results:SearchResult, ttl:int = 3600):
        try:
            await redis_client.setex(search_id, ttl, json.dumps(results))
        except Exception as e:
            logger.warning(f"Redis SET failed: {e}")

