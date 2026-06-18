import httpx
import time
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


# =========================
# CORE INVOICE CREATOR
# =========================
async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    # =========================
    # SAFE AMOUNT
    # =========================
    try:
        amount = int(str(amount).replace(".", "").replace(",", ""))
    except:
        print("❌ INVALID AMOUNT:", amount)
        return None

    if amount <= 0:
        print("❌ AMOUNT INVALID:", amount)
        return None

    external_id = f"{user_id}_{code}_{int(time.time() * 1000)}"

    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": amount,
        "description": f"Purchase file {code}",
        "payment_url": "https://www.bayar.gg/pay",
        "callback_url": "https://earnfilebot.railway.app/bayargg/webhook",
        "payment_method": "qris",
        "external_id": external_id
    }

    headers = {
        "X-API-Key": str(BAYARGG_API_KEY).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)

        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)

        if r.status_code != 200:
            return None

        data = r.json()

        if not isinstance(data, dict):
            return None

        # =========================
        # FLEXIBLE SUCCESS CHECK (FIX IMPORTANT)
        # =========================
        if not (data.get("success") or data.get("status")):
            print("❌ BAYARGG ERROR:", data)
            return None

        result = data.get("data") or {}

        if not isinstance(result, dict):
            return None

        return {
            "invoice_id": result.get("invoice_id") or result.get("id"),
            "qris_string": result.get("qris_string"),
            "payment_url": (
                result.get("payment_url")
                or result.get("checkout_url")
                or result.get("url")
            ),
            "external_id": external_id,
            "raw": result
        }

    except httpx.RequestError as e:
        print("❌ REQUEST ERROR:", e)
        return None

    except Exception as e:
        print("❌ UNKNOWN ERROR:", e)
        return None


# =========================
# COMPAT WRAPPER (JANGAN DIHAPUS)
# =========================
async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
