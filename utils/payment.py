import httpx
import time
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):

    # =========================
    # VALIDASI AMOUNT (INI WAJIB)
    # =========================
    try:
        amount = int(amount)
    except:
        return None

    if amount < 1000:
        print("❌ AMOUNT TOO SMALL:", amount)
        return None

    # =========================
    # UNIQUE EXTERNAL ID
    # =========================
    external_id = f"{user_id}_{code}_{int(time.time())}"

    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": amount,
        "description": f"Purchase file {code}",

        # WAJIB BAYARGG
        "payment_url": "https://www.bayar.gg/pay",

        # WAJIB biar webhook stabil
        "callback_url": "https://earnfilebot.railway.app/bayargg/webhook",

        "payment_method": "qris",

        # optional tapi bagus
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
        print("PAYLOAD:", payload)

        if r.status_code != 200:
            return None

        data = r.json()

        if not data.get("success"):
            print("❌ BAYARGG ERROR:", data)
            return None

        result = data.get("data") or {}

        if not isinstance(result, dict):
            return None

        return {
            "invoice_id": result.get("invoice_id") or result.get("id"),
            "qris_string": result.get("qris_string"),
            "checkout_url": (
                result.get("payment_url")
                or result.get("checkout_url")
                or result.get("invoice_url")
                or result.get("url")
            ),
            "reference": external_id,
            "raw": result
        }

    except httpx.RequestError as e:
        print("❌ REQUEST ERROR:", e)
        return None

    except Exception as e:
        print("❌ UNKNOWN ERROR:", e)
        return None


# alias
async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
