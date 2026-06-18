import json


def extract_qris(invoice):
    if not invoice:
        return None

    # =========================
    # DICT HANDLING
    # =========================
    if isinstance(invoice, dict):

        # direct key
        q = invoice.get("qris_string")
        if q:
            return q

        # common wrappers
        for key in ("data", "result", "payload"):
            sub = invoice.get(key)

            if isinstance(sub, dict):
                q = sub.get("qris_string")
                if q:
                    return q

                # nested deeper layer
                for k2 in ("data", "result"):
                    sub2 = sub.get(k2)
                    if isinstance(sub2, dict):
                        q = sub2.get("qris_string")
                        if q:
                            return q

            # string JSON
            if isinstance(sub, str):
                try:
                    return extract_qris(json.loads(sub))
                except:
                    pass

        return None

    # =========================
    # STRING HANDLING
    # =========================
    if isinstance(invoice, str):
        try:
            return extract_qris(json.loads(invoice))
        except:
            return None

    # =========================
    # LIST HANDLING (API kadang aneh)
    # =========================
    if isinstance(invoice, list):
        for item in invoice:
            q = extract_qris(item)
            if q:
                return q

    return None
