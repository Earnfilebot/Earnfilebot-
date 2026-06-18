import asyncpg
import logging
import asyncio
from config import DATABASE_URL

_pool = None
_lock = asyncio.Lock()


# ========================
# CONNECTION
# ========================
async def get_pool():
    global _pool

    async with _lock:
        if _pool is None or _pool._closed:
            logging.info("🔌 Connecting to database...")

            _pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=1,
                max_size=20,
                command_timeout=60
            )

            logging.info("✅ Database connected")

    return _pool


async def close_db():
    global _pool

    if _pool and not _pool._closed:
        await _pool.close()
        logging.info("🔌 Database closed")


# ========================
# QUERY HELPERS
# ========================
async def execute(query, *args, retry=1):
    for attempt in range(retry + 1):
        try:
            pool = await get_pool()
            return await pool.execute(query, *args)
        except Exception as e:
            logging.error(f"EXECUTE ERROR: {e}")

            if attempt >= retry:
                raise

            await asyncio.sleep(1)


async def fetch(query, *args, retry=1):
    for attempt in range(retry + 1):
        try:
            pool = await get_pool()
            return await pool.fetch(query, *args)
        except Exception as e:
            logging.error(f"FETCH ERROR: {e}")

            if attempt >= retry:
                raise

            await asyncio.sleep(1)


async def fetchrow(query, *args, retry=1):
    for attempt in range(retry + 1):
        try:
            pool = await get_pool()
            return await pool.fetchrow(query, *args)
        except Exception as e:
            logging.error(f"FETCHROW ERROR: {e}")

            if attempt >= retry:
                raise

            await asyncio.sleep(1)


async def fetchval(query, *args, retry=1):
    for attempt in range(retry + 1):
        try:
            pool = await get_pool()
            return await pool.fetchval(query, *args)
        except Exception as e:
            logging.error(f"FETCHVAL ERROR: {e}")

            if attempt >= retry:
                raise

            await asyncio.sleep(1)


# ========================
# TRANSACTION (SUPER IMPORTANT)
# ========================
async def transaction(queries: list):
    """
    queries = [
        ("QUERY SQL", arg1, arg2),
        ("QUERY SQL", arg1)
    ]
    """

    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            results = []

            for q in queries:
                query = q[0]
                args = q[1:]

                result = await conn.execute(query, *args)
                results.append(result)

            return results
