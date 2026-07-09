from datetime import datetime
from zoneinfo import ZoneInfo


# =========================
# TIMEZONE
# =========================

WIB = ZoneInfo("Asia/Jakarta")


# =========================
# WITHDRAW CONFIG
# =========================

WITHDRAW_OPEN_HOUR = 9
WITHDRAW_CLOSE_HOUR = 19


# =========================
# NOMINAL
# =========================

MIN_WITHDRAW = 100_000
WITHDRAW_FEE = 2_000


INSTANT_AMOUNT = 50_000
INSTANT_FEE = 10_000
INSTANT_MIN_BALANCE = INSTANT_AMOUNT + INSTANT_FEE


WITHDRAW_NOMINALS = (
    100_000,
    150_000,
    200_000,
    250_000,
    300_000,
    500_000,
)


# =========================
# CHECK JAM OPERASIONAL
# =========================

def withdraw_is_open() -> bool:
    """
    Withdraw buka:
    Senin - Jumat
    09:00 - 19:00 WIB
    """

    now = datetime.now(WIB)

    # Sabtu Minggu tutup
    if now.weekday() >= 5:
        return False

    return (
        WITHDRAW_OPEN_HOUR
        <= now.hour
        <
        WITHDRAW_CLOSE_HOUR
    )


# =========================
# FORMAT RUPIAH
# =========================

def rupiah(amount: int) -> str:
    return f"Rp {int(amount):,}".replace(",", ".")


# =========================
# MASK NAME
# =========================

def mask_name(name: str) -> str:
    """
    Bayu Anggara
    B**u A*****a
    """

    if not name:
        return "-"

    result = []

    for word in name.split():

        if len(word) <= 2:
            result.append(
                word[0] + "*"
            )

        else:
            result.append(
                word[0]
                +
                "*" * (len(word) - 2)
                +
                word[-1]
            )

    return " ".join(result)


# =========================
# MASK ACCOUNT
# =========================

def mask_account(number: str) -> str:
    """
    081234567890
    0812****7890
    """

    if not number:
        return "-"

    number = str(number)

    if len(number) <= 6:
        return "*" * len(number)

    return (
        number[:4]
        +
        "*" * (len(number) - 8)
        +
        number[-4:]
    )


# =========================
# MASK TELEGRAM ID
# =========================

def mask_id(user_id) -> str:
    """
    6847035364
    684*****364
    """

    if not user_id:
        return "-"

    uid = str(user_id)

    if len(uid) <= 6:
        return "*" * len(uid)

    return (
        uid[:3]
        +
        "*****"
        +
        uid[-3:]
    )
