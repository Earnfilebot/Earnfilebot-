import asyncpg
import logging
import asyncio
from config import DATABASE_URL

_pool = None
_lock = None


def _get_lock():
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


# ========================
# CONNECTION
# ========================
async def get_pool():
    global _pool

    async with _get_lock():
        if _pool is None:
            logging.info("🔌 Connecting to database...")

            _pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=3,
                max_size=30,
                max_inactive_connection_lifetime=300,
                command_timeout=60
            )

            logging.info("✅ Database connected")

    return _pool


async def close_db():
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
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
# TRANSACTION
# ========================
async def transaction(queries: list):
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
