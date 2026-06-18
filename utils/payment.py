import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):
    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    # 🔐 UNIQUE ID (WAJIB FIX)
    external_id = f"{user_id}_{code}_{int(__import__('time').time())}"

    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",
        "payment_url": "https://www.bayar.gg/pay",
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

        data = r.json()

        if r.status_code != 200 or not data.get("success"):
            return None

        result = data.get("data") or {}

        if not isinstance(result, dict):
            return None

        qris_string = result.get("qris_string")

        checkout_url = (
            result.get("payment_url")
            or result.get("checkout_url")
            or result.get("invoice_url")
            or result.get("url")
        )

        invoice_id = (
            result.get("invoice_id")
            or result.get("id")
        )

        return {
            "invoice_id": invoice_id,
            "qris_string": qris_string,
            "checkout_url": checkout_url,
            "reference": external_id,
            "raw": result
        }

    except Exception:
        return None


# alias
async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
