import asyncpg
from config import DATABASE_URL

pool = None


async def connect_db():

    global pool

    if pool is not None:
        return pool

    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=20,
        command_timeout=60
    )

    return pool


async def get_pool():

    global pool

    if pool is None:
        await connect_db()

    return pool


async def close_db():

    global pool

    if pool is not None:

        await pool.close()
        pool = None
