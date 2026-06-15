import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):
    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",
        "payment_url": "https://www.bayar.gg/pay",
        "payment_method": "qris_bayar_gg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "X-API-Key": str(BAYARGG_API_KEY).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:

            # DEBUG PAYMENT METHODS
            test = await client.get(
                f"{BAYARGG_BASE_URL}/payment-methods.php",
                headers={
                    "X-API-Key": str(BAYARGG_API_KEY).strip(),
                    "Accept": "application/json"
                }
            )

            print("===== PAYMENT METHODS =====")
            print("STATUS:", test.status_code)
            print("RESPONSE:", test.text)
            print("===========================")

            # CREATE PAYMENT
            r = await client.post(
                url,
                json=payload,
                headers=headers
            )

        print("===== BAYARGG DEBUG =====")
        print("URL:", url)
        print("PAYLOAD:", payload)
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        if r.status_code != 200:
            return None

        data = r.json()

        if data.get("success") is False:
            print("❌ BAYARGG ERROR:", data)
            return None

        result = data.get("data") or data.get("result") or data

        checkout_url = (
            result.get("checkout_url")
            or result.get("payment_url")
            or result.get("invoice_url")
            or result.get("url")
        )

        reference = (
            result.get("reference")
            or result.get("id")
            or result.get("transaction_id")
            or result.get("external_id")
            or f"{user_id}_{code}"
        )

        if not checkout_url:
            print("❌ CHECKOUT URL TIDAK ADA:", result)
            return None

        return {
            "checkout_url": checkout_url,
            "reference": reference
        }

    except Exception as e:
        print("❌ BAYARGG ERROR:", e)
        return None


async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
