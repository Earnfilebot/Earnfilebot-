from fastapi import FastAPI, Request
from database import get_pool

app = FastAPI()


@app.post("/webhook/bayargg")
async def bayargg_webhook(req: Request):
    data = await req.json()
    print("WEBHOOK MASUK:", data)  # 🔥 DEBUG

    payload = data.get("data", data)

    reference = payload.get("reference")
    status = payload.get("status")

    if not reference or not status:
        print("❌ DATA INVALID")
        return {"ok": False}

    pool = await get_pool()

    if status.lower() == "success":
        await pool.execute(
            """
            UPDATE payments
            SET status='paid'
            WHERE reference=$1
            """,
            reference
        )
        print("✅ PAYMENT UPDATED:", reference)

    else:
        print("⏳ STATUS:", status)

    return {"ok": True}
