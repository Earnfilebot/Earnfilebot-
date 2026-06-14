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
        print("===== BAYARGG DEBUG =====")
        print("URL:", url)
        print("PAYLOAD:", payload)

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.post(url, json=payload, headers=headers)

        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        # =========================
        # RESPONSE KOSONG
        # =========================
        if not r.text:
            print("❌ EMPTY RESPONSE")
            return None

        # =========================
        # PARSE JSON AMAN
        # =========================
        try:
            data = r.json()
        except Exception:
            print("❌ INVALID JSON RESPONSE")
            return None

        # =========================
        # HTTP ERROR
        # =========================
        if r.status_code != 200:
            print("❌ HTTP ERROR:", data)
            return None

        # =========================
        # AMBIL DATA FLEXIBLE
        # =========================
        result = (
            data.get("data")
            or data.get("result")
            or data
        )

        if not isinstance(result, dict):
            print("❌ INVALID RESULT FORMAT:", result)
            return None

        # =========================
        # AMBIL FIELD PAYMENT
        # =========================
        checkout_url = result.get("checkout_url") or result.get("payment_url")
        reference = result.get("reference") or result.get("id")

        # fallback tambahan (kadang API aneh)
        if not checkout_url and isinstance(result, dict):
            checkout_url = result.get("url")

        if not checkout_url or not reference:
            print("❌ MISSING FIELD:", result)
            return None

        print("✅ INVOICE SUCCESS")

        return {
            "checkout_url": checkout_url,
            "reference": reference
        }

    # =========================
    # ERROR HANDLING NETWORK
    # =========================
    except httpx.ConnectError:
        print("❌ DNS / DOMAIN ERROR (bayar.gg tidak bisa diakses)")
        return None

    except httpx.TimeoutException:
        print("❌ TIMEOUT ERROR")
        return None

    except Exception as e:
        print("❌ UNKNOWN ERROR:", e)
        return None
