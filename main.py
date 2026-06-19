from fastapi import FastAPI
import logging

from bot import bot, dp
from webhook.bayargg import router as bayargg_router
from database import get_pool, close_db

app = FastAPI()

# =========================
# ROUTES
# =========================
app.include_router(bayargg_router)

# =========================
# LIFESPAN (FIXED WAY)
# =========================
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):

    # STARTUP
    await get_pool()

    app.state.bot = bot
    app.state.dp = dp   # 🔥 PENTING BANGET

    logging.info("DATABASE CONNECTED")
    logging.info("BOT STARTED (WEBHOOK MODE ONLY)")

    yield

    # SHUTDOWN
    await close_db()
    await bot.session.close()
    logging.info("BOT STOPPED")


app.router.lifespan_context = lifespan


# =========================
# DEBUG ROUTES (OPTIONAL)
# =========================
@app.on_event("startup")
async def debug_routes():
    for r in app.routes:
        print("ROUTE:", r.path)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
