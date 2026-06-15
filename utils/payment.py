import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):
    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.up.railway.app/webhook/bayargg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "X-API-Key": str(BAYARGG_API_KEY).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)

        print("===== BAYARGG DEBUG =====")
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        if r.status_code != 200:
            print("❌ HTTP ERROR")
            return None

        data = r.json()
        result = data.get("data") or data

        checkout_url = result.get("checkout_url") or result.get("payment_url")
        reference = result.get("reference") or result.get("id")

        if not checkout_url or not reference:
            print("❌ MISSING FIELD")
            return None

        print("✅ INVOICE SUCCESS")

        return {
            "checkout_url": checkout_url,
            "reference": reference
        }

    except httpx.ConnectError:
        print("❌ CONNECTION ERROR")
        return None

    except httpx.TimeoutException:
        print("❌ TIMEOUT ERROR")
        return None

    except Exception as e:
        print("❌ UNKNOWN ERROR:", str(e))
        return None
