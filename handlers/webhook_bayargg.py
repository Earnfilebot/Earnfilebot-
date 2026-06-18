import json

from database import get_pool
from fastapi import Request
from config import GROUP_ID

from aiogram import Router

router = Router()


@router.post("/bayargg/webhook")
async def bayargg_webhook(request: Request):

    body = await request.body()
    data = json.loads(body.decode())

    external_id = data.get("external_id")
    status = data.get("status")

    if status != "paid":
        return {"status": "ignored"}

    pool = await get_pool()

    # =========================
    # GET INVOICE
    # =========================
    invoice = await pool.fetchrow(
        "SELECT * FROM invoices WHERE external_id=$1",
        external_id
    )

    if not invoice:
        return {"status": "not found"}

    # =========================
    # 🔥 ANTI DOUBLE CORE (IMPORTANT)
    # =========================
    if invoice["processed"]:
        return {"status": "already processed"}

    # langsung LOCK supaya tidak race condition
    await pool.execute(
        """
        UPDATE invoices
        SET processed = TRUE
        WHERE external_id = $1 AND processed = FALSE
        """,
        external_id
    )

    # re-check (double safety)
    check = await pool.fetchrow(
        "SELECT processed FROM invoices WHERE external_id=$1",
        external_id
    )

    if not check or not check["processed"]:
        return {"status": "blocked race"}

    # =========================
    # MARK PAID
    # =========================
    await pool.execute(
        """
        UPDATE invoices
        SET status='paid', paid_at=NOW()
        WHERE external_id=$1
        """,
        external_id
    )

    # =========================
    # AUTO ADD BALANCE
    # =========================
    await pool.execute(
        """
        UPDATE users
        SET balance = COALESCE(balance, 0) + $1
        WHERE telegram_id = $2
        """,
        invoice["amount"],
        invoice["user_id"]
    )

    # =========================
    # AUTO UNLOCK FILE
    # =========================
    await pool.execute(
        """
        INSERT INTO user_access (user_id, code, paid)
        VALUES ($1, $2, TRUE)
        ON CONFLICT DO NOTHING
        """,
        invoice["user_id"],
        invoice["code"]
    )

    # =========================
    # POST KE GROUP
    # =========================
    bot = request.app["bot"]

    try:
        await bot.send_message(
            GROUP_ID,
            f"🛒 NEW PURCHASE\n\n"
            f"👤 User: {invoice['user_id']}\n"
            f"📦 Code: {invoice['code']}\n"
            f"💰 Amount: Rp {invoice['amount']}"
        )
    except Exception as e:
        print("GROUP ERROR:", repr(e))

    # =========================
    # NOTIF USER
    # =========================
    try:
        await bot.send_message(
            invoice["user_id"],
            f"✅ PAYMENT SUCCESS\n\n"
            f"💰 +Rp {invoice['amount']}\n"
            f"🔓 File `{invoice['code']}` unlocked"
        )
    except:
        pass

    return {"status": "success"}
