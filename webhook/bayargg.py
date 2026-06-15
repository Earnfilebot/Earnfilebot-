from fastapi import FastAPI, Request
from database import get_pool
from bot import bot
from utils.helpers import parse_reference
import json

app = FastAPI()

# =========================
# REALTIME UNLOCK WEBHOOK
# =========================
@app.post("/webhook/bayargg")
async def bayargg_webhook(req: Request):
    data = await req.json()
    print("🔥 WEBHOOK IN:", data)

    payload = data.get("data", data)

    reference = payload.get("reference")
    status = payload.get("status")

    if not reference or not status:
        return {"ok": False}

    user_id, code = parse_reference(reference)

    if not user_id or not code:
        return {"ok": False}

    pool = await get_pool()

    # =========================
    # ONLY SUCCESS PAYMENT
    # =========================
    if status.upper() in ("PAID", "SUCCESS", "SETTLED"):

        # 🔒 lock anti double update
        already_paid = await pool.fetchval(
            "SELECT status FROM payments WHERE reference=$1",
            reference
        )

        if already_paid == "paid":
            return {"ok": True}

        # =========================
        # UPDATE PAYMENT
        # =========================
        await pool.execute("""
            UPDATE payments
            SET status='paid'
            WHERE user_id=$1 AND code=$2
        """, user_id, code)

        # =========================
        # GET FILE DATA
        # =========================
        file = await pool.fetchrow(
            "SELECT * FROM files WHERE code=$1",
            code
        )

        if not file:
            return {"ok": True}

        media = file.get("media") or []

        if isinstance(media, str):
            try:
                media = json.loads(media)
            except:
                media = []

        # =========================
        # REALTIME UNLOCK
        # =========================
        try:
            await bot.send_message(
                user_id,
                "✅ PAYMENT SUCCESS\n🔓 FILE UNLOCKED"
            )

            for m in media[:10]:
                await bot.send_document(user_id, m["file_id"])

        except Exception as e:
            print("SEND ERROR:", e)

    return {"ok": True}
