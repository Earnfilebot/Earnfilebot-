import time
import asyncio
import httpx

from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


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
    # UNIQUE ID (IMPORTANT FOR WEBHOOK)
    # =========================
    external_id = f"{user_id}_{code}_{int(time.time() * 1000)}"

    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": amount,
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.railway.app/bayargg/webhook",
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
    # RETRY SYSTEM (ANTI ERROR API)
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
    # PARSE RESPONSE
    # =========================
    try:
        data = r.json()
    except Exception as e:
        print("❌ INVALID JSON:", repr(e))
        print("RAW:", r.text)
        return None

    # =========================
    # SUCCESS CHECK (FLEXIBLE)
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
# WRAPPER (INI YANG DIPAKAI HANDLER KAMU)
# =========================
async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
