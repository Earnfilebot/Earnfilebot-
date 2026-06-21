import time
import asyncio
import httpx

from config import BAYARGG_API_KEY, BAYARGG_BASE_URL
from database import get_pool   # ✅ FIX WAJIB


# =========================
# SIMPLE ANTI SPAM CACHE
# =========================
_LAST_CALL = {}


async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    # =========================
    # NORMALIZE AMOUNT
    # =========================
    try:
        amount = int(str(amount).replace(".", "").replace(",", ""))
    except Exception:
        print("❌ INVALID AMOUNT:", amount)
        return None

    if amount <= 0:
        print("❌ AMOUNT INVALID:", amount)
        return None

    # =========================
    # ANTI SPAM
    # =========================
    key = f"{user_id}:{code}"
    now = time.time()

    if key in _LAST_CALL and (now - _LAST_CALL[key] < 3):
        print("⛔ BLOCKED DUPLICATE REQUEST:", key)
        return None

    _LAST_CALL[key] = now

    # =========================
    # UNIQUE ID (WEBHOOK SAFE)
    # =========================
    external_id = f"{user_id}_{code}_{int(time.time())}"

    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": amount,
        "description": f"Purchase file {code}",
        "payment_url": "https://earnfileboxbot.com/file.php",
        "payment_method": "qris",
        "external_id": external_id
    }

    headers = {
        "X-API-Key": str(BAYARGG_API_KEY).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    r = None

    # =========================
    # RETRY SYSTEM
    # =========================
    for i in range(2):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(url, json=payload, headers=headers)

            if r.status_code == 200:
                break

        except Exception as e:
            print(f"❌ TRY {i+1} ERROR:", repr(e))
            r = None
            await asyncio.sleep(1)

    if not r:
        print("❌ ALL REQUEST FAILED")
        return None

    if r.status_code != 200:
        print("❌ BAYARGG STATUS:", r.status_code)
        print("❌ RESPONSE:", r.text)
        return None

    # =========================
    # PARSE JSON
    # =========================
    try:
        data = r.json()
    except Exception as e:
        print("❌ INVALID JSON:", repr(e))
        print("RAW:", r.text)
        return None

    if not isinstance(data, dict):
        print("❌ RESPONSE NOT DICT")
        return None

    # =========================
    # SUCCESS CHECK
    # =========================
    if not (
        data.get("success")
        or data.get("status") == "success"
        or data.get("ok") is True
    ):
        print("❌ BAYARGG ERROR:", data)
        return None

    result = data.get("data") or data

    # =========================
    # INSERT PAYMENT (FIXED)
    # =========================
    try:
        async with get_pool() as pool:
            await pool.execute("""
                INSERT INTO payments(user_id, code, status)
                VALUES ($1,$2,'pending')
                ON CONFLICT (user_id, code)
                DO UPDATE SET status='pending'
            """, user_id, code)
    except Exception as e:
        print("❌ DB INSERT ERROR:", repr(e))

    # =========================
    # PAYMENT URL FALLBACK
    # =========================
    payment_url = (
        result.get("payment_url")
        or result.get("checkout_url")
        or result.get("invoice_url")
        or result.get("url")
    )

    return {
        "success": True,
        "invoice_id": result.get("invoice_id") or result.get("id"),
        "qris_string": result.get("qris_string"),
        "payment_url": payment_url,
        "external_id": external_id,
        "raw": result
    }


# =========================
# WRAPPER
# =========================
async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
