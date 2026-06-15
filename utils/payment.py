import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):
    url = f"{BAYARGG_BASE_URL}/create-payment.php"

    payload = {
        "amount": int(amount),
        "description": f"Purchase file {code}",

        # Sesuai docs resmi BayarGG
        "payment_url": "https://www.bayar.gg/pay",
        "payment_method": "qris_bayar_gg",

        # Optional
        "external_id": f"{user_id}_{code}"
    }

    headers = {
        "X-API-Key": str(BAYARGG_API_KEY).strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
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

        try:
            data = r.json()
        except Exception:
            print("❌ INVALID JSON RESPONSE")
            return None

        if data.get("success") is False:
            print("❌ BAYARGG ERROR:", data)
            return None

        result = data.get("data") or data.get("result") or data

        if not isinstance(result, dict):
            print("❌ INVALID RESULT:", result)
            return None

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

        print("✅ INVOICE SUCCESS")
        print("CHECKOUT:", checkout_url)
        print("REFERENCE:", reference)

        return {
            "checkout_url": checkout_url,
            "reference": reference
        }

    except httpx.ConnectError as e:
        print("❌ CONNECTION ERROR:", e)
        return None

    except httpx.TimeoutException:
        print("❌ TIMEOUT ERROR")
        return None

    except httpx.RequestError as e:
        print("❌ REQUEST ERROR:", e)
        return None

    except Exception as e:
        print("❌ UNKNOWN ERROR:", e)
        return None


async def create_invoice(amount: int, code: str, user_id: int):
    return await create_bayargg_invoice(amount, code, user_id)
