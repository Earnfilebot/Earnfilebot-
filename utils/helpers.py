def parse_reference(ref: str):
    try:
        user_id, code = ref.split("_", 1)
        return int(user_id), code
    except:
        return None, None
