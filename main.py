from fastapi import FastAPI
from bot import bot
from webhook.bayargg import router as bayargg_router

app = FastAPI()

# =========================
# ATTACH BOT KE APP STATE
# =========================
@app.on_event("startup")
async def startup():
    app.state.bot = bot
