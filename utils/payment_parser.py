import json

def extract_qris(invoice):
    if not invoice:
        return None

    # =========================
    # 1. kalau dict
    # =========================
    if isinstance(invoice, dict):

        # direct level
        q = invoice.get("qris_string")
        if q:
            return q

        # nested common keys
        for key in ("data", "result", "payload"):
            sub = invoice.get(key)

            if isinstance(sub, dict):
                q = sub.get("qris_string")
                if q:
                    return q

            # kalau nested string JSON
            if isinstance(sub, str):
                try:
                    sub = json.loads(sub)
                    if isinstance(sub, dict):
                        q = sub.get("qris_string")
                        if q:
                            return q
                except:
                    pass

    # =========================
    # 2. kalau string JSON
    # =========================
    if isinstance(invoice, str):
        try:
            return extract_qris(json.loads(invoice))
        except:
            return None

    return None
