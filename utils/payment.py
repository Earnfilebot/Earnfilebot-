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
        print("URL:", url)
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        # ❌ HTTP ERROR
        if r.status_code != 200:
            print("❌ HTTP ERROR")
            return None

        # ❌ EMPTY RESPONSE
        if not r.text:
            print("❌ EMPTY RESPONSE")
            return None

        # ❌ SAFE JSON PARSE
        try:
            data = r.json()
        except Exception:
            print("❌ INVALID JSON RESPONSE")
            return None

        # 🔥 FLEXIBLE RESULT PARSING
        result = data.get("data") or data.get("result") or data

        if not isinstance(result, dict):
            print("❌ INVALID RESULT FORMAT")
            return None

        # 🔥 SUPPORT MULTI FIELD (API beda-beda)
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
        )

        # ❌ FIELD CHECK
        if not checkout_url or not reference:
            print("❌ MISSING FIELD:", result)
            return None

        print("✅ INVOICE SUCCESS")

        return {
            "checkout_url": checkout_url,
            "reference": reference
        }

    except httpx.ConnectError as e:
        print("❌ CONNECTION ERROR:", str(e))
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


# =========================
# ALIAS (BIAR GETFILE AMAN)
# =========================
create_invoice = create_bayargg_invoice
