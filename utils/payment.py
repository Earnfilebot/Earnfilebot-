import httpx
from config import BAYARGG_API_KEY, BAYARGG_BASE_URL


async def create_bayargg_invoice(amount: int, code: str, user_id: int):

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

    # 🔥 FIX ENDPOINT
    url = f"{BAYARGG_BASE_URL}/v1/transaction/create"

    try:
        print("===== BAYARGG DEBUG =====")
        print("URL:", url)

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload, headers=headers)

        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text)
        print("=========================")

        # ❌ RESPONSE KOSONG
        if not r.text:
            print("❌ RESPONSE KOSONG")
            return None

        # ❌ PARSE JSON
        try:
            data = r.json()
        except Exception as e:
            print("❌ JSON ERROR:", e)
            return None

        # ❌ STATUS ERROR
        if r.status_code != 200:
            print("❌ HTTP ERROR:", data)
            return None

        # ❌ FORMAT
        if not isinstance(data, dict):
            print("❌ FORMAT BUKAN DICT")
            return None

        # 🔥 SUPPORT MULTI FORMAT API
        result = data.get("data") or data.get("result") or data

        if not isinstance(result, dict):
            print("❌ RESULT INVALID:", result)
            return None

        # 🔥 FLEXIBLE FIELD (biar gak kejebak beda API)
        checkout_url = (
            result.get("checkout_url")
            or result.get("payment_url")
            or result.get("invoice_url")
        )

        reference = (
            result.get("reference")
            or result.get("id")
            or result.get("external_id")
        )

        if not checkout_url or not reference:
            print("❌ DATA INVOICE TIDAK LENGKAP:", result)
            return None

        print("✅ INVOICE BERHASIL")
        return {
            "checkout_url": checkout_url,
            "reference": reference
        }

    except httpx.ConnectError:
        print("❌ GAGAL KONEK KE BAYARGG (DNS / DOMAIN SALAH)")
        return None

    except httpx.TimeoutException:
        print("❌ TIMEOUT KE BAYARGG")
        return None

    except Exception as e:
        print("❌ INVOICE ERROR:", e)
        return None
