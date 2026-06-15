def extract_qris(invoice: dict):
    if not isinstance(invoice, dict):
        return None

    # format 1: langsung
    if invoice.get("qris_string"):
        return invoice["qris_string"]

    # format 2: nested data
    data = invoice.get("data")
    if isinstance(data, dict):
        if data.get("qris_string"):
            return data["qris_string"]

    return None
