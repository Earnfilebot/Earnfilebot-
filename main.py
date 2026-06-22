from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from bot import bot, dp
from database import get_pool, close_db
from webhook.bayargg import router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 START APP")

    try:
        await get_pool()
    except Exception as e:
        logging.error(f"DB ERROR: {e}")

    app.state.bot = bot
    app.state.dp = dp

    logging.info("🤖 READY")

    yield

    await close_db()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)

app.include_router(router)


@app.get("/")
async def root():
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}
