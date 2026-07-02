import os
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

# =========================
# REDIS CONFIG
# =========================
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    logger.warning("⚠️ REDIS_URL tidak ditemukan! Redis disabled.")
    redis_client = None
else:
    try:
        redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )

        logger.info("✅ Redis connected successfully")

    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        redis_client = None


# =========================
# SAFE WRAPPER (ANTI CRASH)
# =========================
async def safe_set(key: str, value: str, ex: int = None, nx: bool = False):
    """
    Safe Redis SET (tidak bikin bot crash kalau Redis down)
    """
    if not redis_client:
        return True  # fallback aman

    try:
        return await redis_client.set(key, value, ex=ex, nx=nx)
    except Exception as e:
        logger.warning(f"Redis SET failed: {e}")
        return True


async def safe_get(key: str):
    if not redis_client:
        return None

    try:
        return await redis_client.get(key)
    except Exception as e:
        logger.warning(f"Redis GET failed: {e}")
        return None


async def safe_delete(key: str):
    if not redis_client:
        return True

    try:
        return await redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Redis DEL failed: {e}")
        return True
