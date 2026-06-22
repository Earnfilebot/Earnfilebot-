import time
import asyncio
import httpx

from config import BAYARGG_API_KEY, BAYARGG_BASE_URL
from database import get_pool

_LAST_CALL = {}

async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    try:
        amount = int(str(amount).replace(".", "").replace(",", ""))
    except:
        return None

    if amount <= 0:
        return None

    key = f"{user_id}:{code}"
    now = time.time()

    if key in _LAST_CALL and (now - _LAST_CALL[key] < 3):
        return None

    _LAST_CALL[key] = now

    external_id = f"{user_id}_{code}_{int(time.time())}"

    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": amount,
        "description": f"Purchase file {code}",
        "payment_method": "qris",
        "external_id": external_id
    }

    headers = {
        "X-API-Key": str(BAYARGG_API_KEY).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)

    if r.status_code != 200:
        print("❌ BAYARGG ERROR:", r.text)
        return None

    data = r.json()
    result = data.get("data") or data

    invoice_id = result.get("invoice_id") or result.get("id")

    pool = await get_pool()

    await pool.execute("""
        INSERT INTO payments(user_id, code, status, invoice_id, external_id)
        VALUES ($1,$2,'pending',$3,$4)
        ON CONFLICT (user_id, code)
        DO UPDATE SET
            status='pending',
            invoice_id=EXCLUDED.invoice_id,
            external_id=EXCLUDED.external_id
    """, user_id, code, invoice_id, external_id)

    return {
        "invoice_id": invoice_id,
        "external_id": external_id,
        "payment_url": result.get("payment_url") or result.get("url"),
        "qris": result.get("qris_string"),
        "raw": result
    }


async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
