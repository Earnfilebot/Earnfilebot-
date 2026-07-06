import logging
import os

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# =========================
# REDIS INIT
# =========================
REDIS_URL = os.getenv("REDIS_URL")

redis_client = None

if not REDIS_URL:
    logger.warning("⚠️ REDIS_URL not found, Redis disabled")
else:
    try:
        redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        logger.info("✅ Redis initialized")

    except Exception:
        logger.exception("❌ Failed to initialize Redis")
        redis_client = None


# =========================
# SAFE WRAPPERS
# =========================
async def safe_set(
    key: str,
    value: str,
    ex: int | None = None,
    nx: bool = False,
):
    if redis_client is None:
        return False

    try:
        return await redis_client.set(
            key,
            value,
            ex=ex,
            nx=nx,
        )

    except Exception:
        logger.exception("Redis SET failed")
        return False


async def safe_get(key: str):
    if redis_client is None:
        return None

    try:
        return await redis_client.get(key)

    except Exception:
        logger.exception("Redis GET failed")
        return None


async def safe_delete(key: str):
    if redis_client is None:
        return False

    try:
        return await redis_client.delete(key)

    except Exception:
        logger.exception("Redis DELETE failed")
        return False
