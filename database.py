import asyncio
import logging

import asyncpg

from config import DATABASE_URL

_pool = None
_lock = asyncio.Lock()


# ========================
# CONNECTION
# ========================
async def get_pool():
    global _pool

    if _pool is not None:
        return _pool

    async with _lock:
        if _pool is not None:
            return _pool

        while True:
            try:
                logging.info("🔌 Connecting to PostgreSQL...")

                _pool = await asyncpg.create_pool(
                    dsn=DATABASE_URL,
                    min_size=3,
                    max_size=30,
                    command_timeout=60,
                    max_inactive_connection_lifetime=300
                )

                logging.info("✅ PostgreSQL connected")
                break

            except Exception:
                logging.exception(
                    "❌ Failed connecting to PostgreSQL. Retrying in 3 seconds..."
                )
                await asyncio.sleep(3)

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

            async with pool.acquire() as conn:
                return await conn.execute(query, *args)

        except Exception:
            logging.exception("EXECUTE ERROR")

            if attempt >= retry:
                raise

            await asyncio.sleep(1)


async def fetch(query, *args, retry=1):
    for attempt in range(retry + 1):
        try:
            pool = await get_pool()

            async with pool.acquire() as conn:
                return await conn.fetch(query, *args)

        except Exception:
            logging.exception("FETCH ERROR")

            if attempt >= retry:
                raise

            await asyncio.sleep(1)


async def fetchrow(query, *args, retry=1):
    for attempt in range(retry + 1):
        try:
            pool = await get_pool()

            async with pool.acquire() as conn:
                return await conn.fetchrow(query, *args)

        except Exception:
            logging.exception("FETCHROW ERROR")

            if attempt >= retry:
                raise

            await asyncio.sleep(1)


async def fetchval(query, *args, retry=1):
    for attempt in range(retry + 1):
        try:
            pool = await get_pool()

            async with pool.acquire() as conn:
                return await conn.fetchval(query, *args)

        except Exception:
            logging.exception("FETCHVAL ERROR")

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

                results.append(
                    await conn.execute(query, *args)
                )

            return results
