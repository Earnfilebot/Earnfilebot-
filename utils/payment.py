import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):
    url = f"{BAYARGG_BASE_URL}/transaction/create"

    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",
        "callback_url": "https://earnfilebot.up.railway.app/webhook/bayargg",
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "Authorization": f"Bearer {BAYARGG_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.post(url, json=payload, headers=headers)

        print("===== BAYARGG DEBUG =====")
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        if not r.text:
            print("❌ EMPTY RESPONSE")
            return None

        try:
            data = r.json()
        except Exception:
            print("❌ INVALID JSON RESPONSE")
            return None

        if r.status_code != 200:
            print("❌ HTTP ERROR:", data)
            return None

        result = data.get("data") or data.get("result") or data

        if not isinstance(result, dict):
            print("❌ INVALID RESULT FORMAT:", result)
            return None

        checkout_url = (
            result.get("checkout_url")
            or result.get("payment_url")
            or result.get("url")
        )

        reference = (
            result.get("reference")
            or result.get("id")
            or result.get("transaction_id")
        )

        if not checkout_url or not reference:
            print("❌ MISSING FIELD:", result)
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

    except httpx.RequestError as e:
        print("❌ REQUEST ERROR:", str(e))
        return None

    except Exception as e:
        print("❌ UNKNOWN ERROR:", str(e))
        return None
