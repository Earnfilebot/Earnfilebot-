import time
import asyncio
import httpx

from config import BAYARGG_API_KEY, BAYARGG_BASE_URL
from database import get_pool


_LAST_CALL = {}


async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    try:
        amount = int(str(amount).replace(".", "").replace(",", ""))
    except Exception:
        print("❌ INVALID AMOUNT:", amount)
        return None

    if amount <= 0:
        print("❌ AMOUNT INVALID:", amount)
        return None

    key = f"{user_id}:{code}"
    now = time.time()

    if key in _LAST_CALL and (now - _LAST_CALL[key] < 3):
        print("⛔ BLOCKED DUPLICATE REQUEST:", key)
        return None

    _LAST_CALL[key] = now

    external_id = f"{user_id}_{code}_{int(time.time())}"

    print("➡️ CREATE INVOICE START", user_id, code, amount)

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

    try:
        data = r.json()
    except Exception as e:
        print("❌ INVALID JSON:", repr(e))
        return None

    print("➡️ BAYARGG RESPONSE:", data)

    if not isinstance(data, dict):
        return None

    if not (data.get("success") or data.get("status") == "success" or data.get("ok") is True):
        print("❌ BAYARGG ERROR:", data)
        return None

    result = data.get("data") or data

    # =========================
    # FIXED DB INSERT
    # =========================
    try:
        pool = await get_pool()

        await pool.execute(
            """
            INSERT INTO payments(user_id, code, status)
            VALUES ($1,$2,'pending')
            ON CONFLICT (user_id, code)
            DO UPDATE SET status='pending'
            """,
            user_id,
            code
        )

    except Exception as e:
        print("❌ DB INSERT ERROR:", repr(e))

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


async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
