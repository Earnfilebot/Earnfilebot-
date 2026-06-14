from fastapi import FastAPI, Request
from database import get_pool

app = FastAPI()


@app.post("/webhook/bayargg")
async def bayargg_webhook(req: Request):

    data = await req.json()

    reference = data["reference"]
    status = data["status"]

    pool = await get_pool()

    if status == "success":

        await pool.execute(
            """
            UPDATE payments
            SET status='paid'
            WHERE reference=$1
            """,
            reference
        )

    return {"ok": True}
