from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from database import get_pool
from states.withdraw import WithdrawState
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_IDS

router = Router()

logger = logging.getLogger(__name__)

# =========================
# CONFIG
# =========================

WIB = ZoneInfo("Asia/Jakarta")

WITHDRAW_OPEN_HOUR = 9
WITHDRAW_CLOSE_HOUR = 19

# =========================
# WITHDRAW INSTANT
# =========================

INSTANT_AMOUNT = 50_000
INSTANT_FEE = 10_000
INSTANT_MIN_BALANCE = INSTANT_AMOUNT + INSTANT_FEE


# =========================
# CEK JAM OPERASIONAL
# =========================

class WithdrawState(StatesGroup):
    confirm_withdraw = State()
    confirm_instant = State()

def withdraw_is_open() -> bool:
    """
    Withdraw buka:
    Senin - Jumat
    09:00 - 19:00 WIB
    """

    now = datetime.now(WIB)

    # Sabtu & Minggu tutup
    if now.weekday() >= 5:
        return False

    return WITHDRAW_OPEN_HOUR <= now.hour < WITHDRAW_CLOSE_HOUR

# =========================
# MASK DATA CHANNEL
# =========================

def mask_name(name: str) -> str:
    """
    Contoh:
    Bayu Anggara
    menjadi:
    B**u A*****a
    """

    if not name:
        return "-"

    result = []

    for word in name.split():

        if len(word) <= 2:
            result.append(word[0] + "*")

        else:
            result.append(
                word[0]
                + "*" * (len(word) - 2)
                + word[-1]
            )

    return " ".join(result)



def mask_account(number: str) -> str:
    """
    Contoh:
    081234567890
    menjadi:
    0812****7890
    """

    if not number:
        return "-"

    number = str(number)

    if len(number) <= 6:
        return "*" * len(number)

    return (
        number[:4]
        + "*" * (len(number) - 8)
        + number[-4:]
    )



def mask_id(user_id) -> str:
    """
    Contoh:
    6847035364
    menjadi:
    684*****364
    """

    if not user_id:
        return "-"

    uid = str(user_id)

    if len(uid) <= 6:
        return "*" * len(uid)

    return (
        uid[:3]
        + "*****"
        + uid[-3:]
    )
# =========================
# MENU WITHDRAW
# =========================

@router.callback_query(F.data == "withdraw")
async def withdraw_menu(
    call: CallbackQuery,
    state: FSMContext
):
    await call.answer()

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🏦 Rekening / E-Wallet",
        callback_data="withdraw_account"
    )

    if withdraw_is_open():

        status = "🟢 <b>BUKA</b>"

        kb.button(
            text="💸 Withdraw Reguler",
            callback_data="withdraw_create"
        )

        kb.button(
            text="⚡ Withdraw Instant",
            callback_data="withdraw_instant"
        )

    else:

        status = "🔴 <b>TUTUP</b>"

        kb.button(
            text="🔒 Withdraw Sedang Tutup",
            callback_data="withdraw_closed"
        )

    kb.button(
        text="📜 Riwayat Withdraw",
        callback_data="withdraw_history"
    )

    kb.button(
        text="🔙 Kembali",
        callback_data="home"
    )

    kb.adjust(1)

    text = (
        "💸 <b>WITHDRAW SALDO</b>\n"
        "━━━━━━━━━━━━━━\n\n"

        f"📌 Status Layanan : {status}\n\n"

        "🕘 <b>Jam Operasional</b>\n"
        "• Senin - Jumat\n"
        "• 09:00 - 19:00 WIB\n"
        "• Sabtu & Minggu Libur\n\n"

        "🏦 <b>Rekening / E-Wallet</b>\n"
        "Tambahkan rekening tujuan terlebih dahulu sebelum melakukan withdraw.\n\n"

        "💰 <b>Withdraw Reguler</b>\n"
        "• Minimal Withdraw : Rp100.000\n"
        "• Fee Admin : Rp2.000\n"
        "• Diproses sesuai antrean admin.\n\n"

        "⚡ <b>Withdraw Instant</b>\n"
        "• Minimal Saldo : Rp60.000\n"
        "• Nominal Tetap : Rp50.000\n"
        "• Diprioritaskan dibanding reguler.\n"
        "• Diproses lebih cepat."
    )

    try:
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    except TelegramBadRequest as e:

        # Abaikan MessageNotModified
        if "message is not modified" not in str(e).lower():
            logger.exception(e)

# =========================
# WITHDRAW REGULER
# =========================

MIN_WITHDRAW = 100_000
WITHDRAW_FEE = 2_000

WITHDRAW_NOMINALS = (
    100_000,
    150_000,
    200_000,
    250_000,
    300_000,
    500_000,
)


@router.callback_query(F.data == "withdraw_create")
async def withdraw_create(
    call: CallbackQuery,
    state: FSMContext
):
    await call.answer()

    # =========================
    # CEK JAM OPERASIONAL
    # =========================

    if not withdraw_is_open():

        kb = InlineKeyboardBuilder()
        kb.button(
            text="🔙 Kembali",
            callback_data="withdraw"
        )

        try:
            await call.message.edit_text(
                (
                    "🔒 <b>Layanan Withdraw Sedang Tutup</b>\n\n"
                    "Jam Operasional:\n"
                    "• Senin - Jumat\n"
                    "• 09:00 - 19:00 WIB\n"
                    "• Sabtu & Minggu Libur"
                ),
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.exception(e)

        return

    pool = await get_pool()

    # =========================
    # AMBIL REKENING DEFAULT
    # =========================

    account = await pool.fetchrow(
        """
        SELECT
            uwa.id,
            uwa.account_name,
            uwa.account_number,
            wm.name AS method_name
        FROM user_withdraw_accounts AS uwa
        JOIN withdraw_methods AS wm
            ON wm.id = uwa.method_id
        WHERE
            uwa.user_id = $1
            AND uwa.is_default = TRUE
        LIMIT 1
        """,
        call.from_user.id
    )

    if account is None:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="➕ Tambah Rekening",
            callback_data="withdraw_add_account"
        )

        kb.button(
            text="🔙 Menu Withdraw",
            callback_data="withdraw"
        )

        kb.adjust(1)

        try:
            await call.message.edit_text(
                (
                    "❌ <b>Rekening Default Belum Ada</b>\n\n"
                    "Silakan tambahkan rekening atau E-Wallet "
                    "terlebih dahulu sebelum melakukan withdraw."
                ),
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.exception(e)

        return

    # =========================
    # CEK SALDO
    # =========================

    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id = $1
        """,
        call.from_user.id
    ) or 0

    minimum_balance = MIN_WITHDRAW + WITHDRAW_FEE

    if balance < minimum_balance:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="🔙 Menu Withdraw",
            callback_data="withdraw"
        )

        try:
            await call.message.edit_text(
                (
                    "❌ <b>Saldo Tidak Mencukupi</b>\n\n"
                    f"Minimal saldo untuk withdraw reguler adalah\n"
                    f"<b>Rp {minimum_balance:,}</b>\n\n"
                    f"(Rp {MIN_WITHDRAW:,} + "
                    f"Fee Rp {WITHDRAW_FEE:,})"
                ).replace(",", "."),
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.exception(e)

        return

    # =========================
    # RESET SESSION
    # =========================

    await state.clear()

    await state.update_data(
        withdraw_account_id=account["id"],
        withdraw_fee=WITHDRAW_FEE
    )

    # =========================
    # KEYBOARD NOMINAL
    # =========================

    kb = InlineKeyboardBuilder()

    for nominal in WITHDRAW_NOMINALS:
        kb.button(
            text=f"💸 Rp {nominal:,}".replace(",", "."),
            callback_data=f"wd_amount:{nominal}"
        )

    kb.button(
        text="❌ Batal",
        callback_data="withdraw"
    )

    kb.adjust(2, 2, 2, 1)

    # =========================
    # TAMPILKAN MENU
    # =========================

    text = (
        "💸 <b>WITHDRAW REGULER</b>\n"
        "━━━━━━━━━━━━━━\n\n"

        f"💰 Saldo Saat Ini\n"
        f"<b>Rp {balance:,}</b>\n\n"

        "<b>🏦 Rekening Tujuan</b>\n"
        f"Metode : {account['method_name']}\n"
        f"Nama : {account['account_name']}\n"
        f"No. Rekening : "
        f"<code>{account['account_number']}</code>\n\n"

        f"💸 Fee Admin : "
        f"<b>Rp {WITHDRAW_FEE:,}</b>\n"

        f"💵 Minimal Withdraw : "
        f"<b>Rp {MIN_WITHDRAW:,}</b>\n\n"

        "👇 Silakan pilih nominal withdraw."
    ).replace(",", ".")

    try:
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.exception(e)

# =========================
# PILIH NOMINAL WITHDRAW
# =========================

@router.callback_query(F.data.startswith("wd_amount:"))
async def withdraw_amount(
    call: CallbackQuery,
    state: FSMContext
):
    await call.answer()

    # =========================
    # VALIDASI CALLBACK
    # =========================

    try:
        amount = int(call.data.split(":", 1)[1])

    except (ValueError, IndexError):
        return await call.answer(
            "Nominal tidak valid.",
            show_alert=True
        )

    # Anti edit callback_data
    if amount not in WITHDRAW_NOMINALS:
        return await call.answer(
            "Nominal tidak valid.",
            show_alert=True
        )

    # =========================
    # CEK SESSION
    # =========================

    data = await state.get_data()

    account_id = data.get("withdraw_account_id")

    if not account_id:
        return await call.answer(
            "Session withdraw telah berakhir. Silakan ulangi kembali.",
            show_alert=True
        )

    fee = int(data.get("withdraw_fee", WITHDRAW_FEE))
    total = amount + fee

    # =========================
    # CEK SALDO TERBARU
    # =========================

    pool = await get_pool()

    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id = $1
        """,
        call.from_user.id
    ) or 0

    if balance < total:
        return await call.answer(
            (
                "❌ Saldo tidak mencukupi.\n\n"
                f"Dibutuhkan Rp {total:,}"
            ).replace(",", "."),
            show_alert=True
        )

    # =========================
    # SIMPAN SESSION
    # =========================

    await state.update_data(
        withdraw_amount=amount,
        withdraw_total=total
    )

    await state.set_state(
        WithdrawState.confirm_withdraw
    )

    # =========================
    # KEYBOARD
    # =========================

    kb = InlineKeyboardBuilder()

    kb.button(
        text="✅ Konfirmasi",
        callback_data="withdraw_confirm"
    )

    kb.button(
        text="❌ Batal",
        callback_data="withdraw_cancel"
    )

    kb.adjust(1)

    # =========================
    # TAMPILKAN KONFIRMASI
    # =========================

    text = (
        "💸 <b>KONFIRMASI WITHDRAW</b>\n"
        "━━━━━━━━━━━━━━\n\n"

        f"💰 Nominal : <b>Rp {amount:,}</b>\n"
        f"💸 Fee Telegram : <b>Rp {fee:,}</b>\n"
        f"📉 Total Dipotong : <b>Rp {total:,}</b>\n\n"

        "Pastikan data rekening sudah benar.\n"
        "Tekan tombol <b>Konfirmasi</b> untuk melanjutkan."
    ).replace(",", ".")

    try:
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.exception(e)

# =========================
# WITHDRAW INSTANT
# =========================

@router.callback_query(F.data == "withdraw_instant")
async def withdraw_instant(
    call: CallbackQuery,
    state: FSMContext
):
    await call.answer()

    # =========================
    # CEK JAM OPERASIONAL
    # =========================

    if not withdraw_is_open():

        kb = InlineKeyboardBuilder()

        kb.button(
            text="🔙 Menu Withdraw",
            callback_data="withdraw"
        )

        return await call.message.edit_text(
            (
                "🔒 <b>Layanan Withdraw Instant Sedang Tutup</b>\n\n"
                "Jam Operasional\n"
                "• Senin -Jumat\n"
                "• 09:00 - 19:00 WIB\n"
                "• Sabtu & Minggu Libur"
            ),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    pool = await get_pool()

    # =========================
    # REKENING DEFAULT
    # =========================

    account = await pool.fetchrow(
        """
        SELECT
            uwa.id,
            uwa.account_name,
            uwa.account_number,
            wm.name AS method_name
        FROM user_withdraw_accounts uwa
        JOIN withdraw_methods wm
            ON wm.id = uwa.method_id
        WHERE
            uwa.user_id=$1
            AND uwa.is_default=TRUE
        LIMIT 1
        """,
        call.from_user.id
    )

    if account is None:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="➕ Tambah Rekening",
            callback_data="withdraw_add_account"
        )

        kb.button(
            text="🔙 Menu Withdraw",
            callback_data="withdraw"
        )

        kb.adjust(1)

        return await call.message.edit_text(
            (
                "❌ <b>Rekening Default Belum Ada</b>\n\n"
                "Tambahkan rekening atau E-Wallet terlebih dahulu."
            ),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    # =========================
    # SALDO USER
    # =========================

    balance = await pool.fetchval(
        """
        SELECT balance
        FROM users
        WHERE telegram_id=$1
        """,
        call.from_user.id
    ) or 0

    if balance < INSTANT_MIN_BALANCE:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="🔙 Menu Withdraw",
            callback_data="withdraw"
        )

        return await call.message.edit_text(
            (
                "❌ <b>Saldo Tidak Mencukupi</b>\n\n"
                f"Minimal saldo untuk Withdraw Instant adalah\n"
                f"<b>Rp {INSTANT_MIN_BALANCE:,}</b>\n\n"
                f"Nominal : Rp {INSTANT_AMOUNT:,}\n"
                f"Fee : Rp {INSTANT_FEE:,}"
            ).replace(",", "."),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    # =========================
    # CEK PENDING
    # =========================

    pending = await pool.fetchval(
        """
        SELECT id
        FROM withdrawals
        WHERE seller_id=$1
        AND status='pending'
        LIMIT 1
        """,
        call.from_user.id
    )

    if pending:

        return await call.answer(
            "Masih ada withdraw yang sedang diproses.",
            show_alert=True
        )

    # =========================
    # RESET SESSION
    # =========================

    await state.clear()

    await state.update_data(
        withdraw_type="instant",
        withdraw_account_id=account["id"],
        withdraw_amount=INSTANT_AMOUNT,
        withdraw_fee=INSTANT_FEE,
        withdraw_total=INSTANT_MIN_BALANCE
    )

    # =========================
    # KEYBOARD
    # =========================

    kb = InlineKeyboardBuilder()

    kb.button(
        text="⚡ Konfirmasi Withdraw Instant",
        callback_data="withdraw_instant_confirm"
    )

    kb.button(
        text="❌ Batal",
        callback_data="withdraw"
    )

    kb.adjust(1)

    # =========================
    # TAMPILKAN
    # =========================

    await call.message.edit_text(
        (
            "⚡ <b>WITHDRAW INSTANT</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            "🚀 Dana diprioritaskan diproses admin.\n\n"

            f"🏦 Metode : {account['method_name']}\n"
            f"👤 Nama : {account['account_name']}\n"
            f"💳 Nomor : <code>{account['account_number']}</code>\n\n"

            f"💰 Saldo : <b>Rp {balance:,}</b>\n"
            f"💵 Nominal : <b>Rp {INSTANT_AMOUNT:,}</b>\n"
            f"💸 Fee Telegram Fast : <b>Rp {INSTANT_FEE:,}</b>\n"
            f"📉 Total Potong : <b>Rp {INSTANT_MIN_BALANCE:,}</b>\n\n"

            "Tekan tombol di bawah untuk melanjutkan."
        ).replace(",", "."),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == "withdraw_instant_confirm")
async def withdraw_instant_confirm(
    call: CallbackQuery,
    state: FSMContext
):
    await call.answer()

    if not withdraw_is_open():
        await state.clear()
        return await call.answer(
            "Jam operasional withdraw telah berakhir.",
            show_alert=True
        )

    data = await state.get_data()

    if data.get("withdraw_processing"):
        return await call.answer(
            "Sedang diproses...",
            show_alert=True
        )

    account_id = data.get("withdraw_account_id")

    # =========================
    # SESSION EXPIRED
    # =========================

    if not account_id:

        await state.clear()

        return await call.answer(
            "Session withdraw expired.\nSilakan ulangi dari menu withdraw.",
            show_alert=True
        )


    await state.update_data(
        withdraw_processing=True
    )


    pool = await get_pool()


    # =========================
    # AMBIL REKENING
    # =========================

    account = await pool.fetchrow(
        """
        SELECT
            uwa.account_name,
            uwa.account_number,
            wm.name AS method_name
        FROM user_withdraw_accounts uwa
        JOIN withdraw_methods wm
            ON wm.id = uwa.method_id
        WHERE
            uwa.id=$1
            AND uwa.user_id=$2
        LIMIT 1
        """,
        account_id,
        call.from_user.id
    )


    if account is None:

        await state.clear()

        return await call.answer(
            "Rekening tidak ditemukan.",
            show_alert=True
        )


    amount = INSTANT_AMOUNT
    fee = INSTANT_FEE
    total = amount + fee


    try:

        async with pool.acquire() as conn:

            async with conn.transaction():


                user = await conn.fetchrow(
                    """
                    SELECT balance
                    FROM users
                    WHERE telegram_id=$1
                    FOR UPDATE
                    """,
                    call.from_user.id
                )


                if not user:

                    await state.clear()

                    return await call.answer(
                        "User tidak ditemukan.",
                        show_alert=True
                    )


                if user["balance"] < total:

                    await state.clear()

                    return await call.answer(
                        "Saldo tidak mencukupi.",
                        show_alert=True
                    )


                pending = await conn.fetchval(
                    """
                    SELECT id
                    FROM withdrawals
                    WHERE seller_id=$1
                    AND status IN (
                        'pending',
                        'instant_pending'
                    )
                    LIMIT 1
                    """,
                    call.from_user.id
                )


                if pending:

                    await state.clear()

                    return await call.answer(
                        "Masih ada withdraw yang diproses.",
                        show_alert=True
                    )


                # potong saldo

                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $1
                    WHERE telegram_id=$2
                    """,
                    total,
                    call.from_user.id
                )


                withdraw_id = await conn.fetchval(
                    """
                    INSERT INTO withdrawals
                    (
                        seller_id,
                        amount,
                        fee,
                        method,
                        account_name,
                        account_number,
                        status,
                        created_at
                    )
                    VALUES
                    (
                        $1,$2,$3,$4,$5,$6,
                        'instant_pending',
                        NOW()
                    )
                    RETURNING id
                    """,
                    call.from_user.id,
                    amount,
                    fee,
                    account["method_name"],
                    account["account_name"],
                    account["account_number"]
                )


                await conn.execute(
                    """
                    INSERT INTO wallet_transactions
                    (
                        telegram_id,
                        type,
                        amount,
                        description,
                        created_at
                    )
                    VALUES
                    (
                        $1,
                        'withdraw_instant',
                        $2,
                        $3,
                        NOW()
                    )
                    """,
                    call.from_user.id,
                    -total,
                    f"Instant Withdraw #{withdraw_id}"
                )


    except Exception as e:

        await state.clear()

        logger.exception(
            "WITHDRAW INSTANT ERROR"
        )

        return await call.answer(
            "Terjadi kesalahan sistem.",
            show_alert=True
        )


    remaining_balance = user["balance"] - total


    await state.clear()


    # lanjutkan kirim notif admin + pesan sukses user di bawah sini

    # =========================
    # NOTIF ADMIN
    # =========================

    created_time = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")

    username = (
        f"@{call.from_user.username}"
        if call.from_user.username
        else "-"
    )

    for admin_id in ADMIN_IDS:

        try:

            kb_admin = InlineKeyboardBuilder()

            kb_admin.button(
                text="✅ Proses",
                callback_data=f"withdraw_process:{withdraw_id}"
            )

            kb_admin.button(
                text="❌ Reject",
                callback_data=f"withdraw_reject:{withdraw_id}"
            )

            kb_admin.adjust(2)

            await call.bot.send_message(
                admin_id,
                (
                    "⚡ <b>REQUEST WITHDRAW INSTANT</b>\n"
                    "━━━━━━━━━━━━━━\n\n"

                    f"🆔 Withdraw ID : <code>{withdraw_id}</code>\n"
                    f"👤 User ID : <code>{call.from_user.id}</code>\n"
                    f"🙍 Nama : <b>{call.from_user.full_name}</b>\n"
                    f"📱 Username : {username}\n\n"

                    f"🏦 Metode : <b>{account['method_name']}</b>\n"
                    f"👤 Nama Rekening : <b>{account['account_name']}</b>\n"
                    f"💳 Nomor : <code>{account['account_number']}</code>\n\n"

                    f"💰 Nominal : <b>Rp {amount:,}</b>\n"
                    f"💸 Fee : <b>Rp {fee:,}</b>\n"
                    f"📉 Total Potong : <b>Rp {total:,}</b>\n"
                    f"💵 Sisa Saldo : <b>Rp {remaining_balance:,}</b>\n\n"

                    f"🕒 Waktu : <b>{created_time} WIB</b>\n"
                    "⚡ <b>PRIORITAS INSTANT</b>\n"
                    "⏳ Status : <b>PENDING</b>"
                ).replace(",", "."),
                parse_mode="HTML",
                reply_markup=kb_admin.as_markup()
            )

        except Exception:
            logger.exception("INSTANT ADMIN NOTIFY ERROR")


    # =========================
    # USER SUCCESS
    # =========================

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📜 Riwayat Withdraw",
        callback_data="withdraw_history"
    )

    kb.button(
        text="🔙 Menu Withdraw",
        callback_data="withdraw"
    )

    kb.adjust(1)

    await call.message.edit_text(
        (
            "⚡ <b>WITHDRAW INSTANT BERHASIL DIBUAT</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🆔 ID Withdraw : <code>{withdraw_id}</code>\n\n"

            f"🏦 Metode : <b>{account['method_name']}</b>\n"
            f"👤 Nama : <b>{account['account_name']}</b>\n"
            f"💳 Nomor : <code>{account['account_number']}</code>\n\n"

            f"💰 Nominal : <b>Rp {amount:,}</b>\n"
            f"💸 Fee : <b>Rp {fee:,}</b>\n"
            f"📉 Total Dipotong : <b>Rp {total:,}</b>\n"
            f"💵 Sisa Saldo : <b>Rp {remaining_balance:,}</b>\n\n"

            "⚡ Permintaan Anda masuk ke antrean PRIORITAS.\n"
            "Admin akan memproses lebih cepat dibanding withdraw reguler."
        ).replace(",", "."),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


# =========================
# KONFIRMASI WITHDRAW
# =========================

@router.callback_query(F.data == "withdraw_confirm")
async def withdraw_confirm(
    call: CallbackQuery,
    state: FSMContext
):
    await call.answer()

    # Jam operasional
    if not withdraw_is_open():
        await state.clear()
        return await call.answer(
            "Jam operasional withdraw telah berakhir.",
            show_alert=True
        )

    data = await state.get_data()

    # Anti spam tombol konfirmasi
    if data.get("withdraw_processing"):
        return

    await state.update_data(withdraw_processing=True)

    if "withdraw_amount" not in data:
        await state.clear()
        return await call.answer(
            "Data withdraw tidak ditemukan.",
            show_alert=True
        )

    pool = await get_pool()

    account = await pool.fetchrow(
        """
        SELECT
            uwa.account_name,
            uwa.account_number,
            wm.name AS method_name
        FROM user_withdraw_accounts uwa
        JOIN withdraw_methods wm
            ON wm.id = uwa.method_id
        WHERE
            uwa.id=$1
            AND uwa.user_id=$2
        """,
        data["withdraw_account_id"],
        call.from_user.id
    )

    if account is None:
        await state.clear()
        return await call.answer(
            "Rekening tidak ditemukan.",
            show_alert=True
        )

    amount = int(data["withdraw_amount"])
    fee = int(data.get("withdraw_fee", 2000))
    total = amount + fee

    try:

        async with pool.acquire() as conn:

            async with conn.transaction():

                # Lock saldo user
                user = await conn.fetchrow(
                    """
                    SELECT balance
                    FROM users
                    WHERE telegram_id=$1
                    FOR UPDATE
                    """,
                    call.from_user.id
                )

                if user is None:
                    await state.clear()
                    return await call.answer(
                        "User tidak ditemukan.",
                        show_alert=True
                    )

                if user["balance"] < total:
                    await state.clear()
                    return await call.answer(
                        "Saldo tidak mencukupi.",
                        show_alert=True
                    )

                # Cegah withdraw ganda
                pending = await conn.fetchval(
                    """
                    SELECT id
                    FROM withdrawals
                    WHERE seller_id=$1
                      AND status='pending'
                    LIMIT 1
                    """,
                    call.from_user.id
                )

                if pending:
                    await state.clear()
                    return await call.answer(
                        "Masih ada withdraw yang sedang diproses.",
                        show_alert=True
                    )

                # Potong saldo
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $1
                    WHERE telegram_id=$2
                    """,
                    total,
                    call.from_user.id
                )

                # Simpan withdraw
                withdraw_id = await conn.fetchval(
                    """
                    INSERT INTO withdrawals
                    (
                        seller_id,
                        amount,
                        fee,
                        method,
                        account_name,
                        account_number,
                        status,
                        created_at
                    )
                    VALUES
                    (
                        $1,$2,$3,$4,$5,$6,
                        'pending',
                        NOW()
                    )
                    RETURNING id
                    """,
                    call.from_user.id,
                    amount,
                    fee,
                    account["method_name"],
                    account["account_name"],
                    account["account_number"]
                )

                # Histori saldo
                await conn.execute(
                    """
                    INSERT INTO wallet_transactions
                    (
                        telegram_id,
                        type,
                        amount,
                        description,
                        created_at
                    )
                    VALUES
                    (
                        $1,
                        'withdraw',
                        $2,
                        $3,
                        NOW()
                    )
                    """,
                    call.from_user.id,
                    -total,
                    f"Withdraw #{withdraw_id}"
                )

    except Exception as e:

        await state.clear()

        print("WITHDRAW CREATE ERROR:", e)

        return await call.answer(
            "Terjadi kesalahan saat membuat withdraw.",
            show_alert=True
        )

    # =========================
    # NOTIF ADMIN
    # =========================

    bot = call.bot

    created_time = datetime.now(WIB).strftime("%d-%m-%Y %H:%M:%S")

    remaining_balance = user["balance"] - total

    for admin_id in ADMIN_IDS:

        try:

            kb_admin = InlineKeyboardBuilder()

            kb_admin.button(
                text="✅ Proses",
                callback_data=f"withdraw_process:{withdraw_id}"
            )

            kb_admin.button(
                text="❌ Reject",
                callback_data=f"withdraw_reject:{withdraw_id}"
            )

            kb_admin.adjust(2)

            username = (
                f"@{call.from_user.username}"
                if call.from_user.username
                else "-"
            )

            await bot.send_message(
                admin_id,
                (
                    "🚨 <b>REQUEST WITHDRAW BARU</b>\n"
                    "━━━━━━━━━━━━━━\n\n"

                    f"🆔 Withdraw ID : <code>{withdraw_id}</code>\n"
                    f"👤 User ID : <code>{call.from_user.id}</code>\n"
                    f"🙍 Nama : <b>{call.from_user.full_name}</b>\n"
                    f"📱 Username : {username}\n\n"

                    f"🏦 Metode : <b>{account['method_name']}</b>\n"
                    f"👤 Nama Rekening : <b>{account['account_name']}</b>\n"
                    f"💳 Nomor : <code>{account['account_number']}</code>\n\n"

                    f"💰 Nominal : <b>Rp {amount:,}</b>\n"
                    f"💸 Fee : <b>Rp {fee:,}</b>\n"
                    f"📉 Total Potong : <b>Rp {total:,}</b>\n"
                    f"💵 Sisa Saldo : <b>Rp {remaining_balance:,}</b>\n\n"

                    f"🕒 Waktu : <b>{created_time} WIB</b>\n"
                    "⏳ Status : <b>PENDING</b>"
                ).replace(",", "."),
                parse_mode="HTML",
                reply_markup=kb_admin.as_markup()
            )

        except Exception as e:
            print(f"WITHDRAW ADMIN NOTIFY ERROR ({admin_id}):", e)

    # Bersihkan FSM
    await state.clear()

    # =========================
    # PESAN SUKSES USER
    # =========================

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📜 Riwayat Withdraw",
        callback_data="withdraw_history"
    )

    kb.button(
        text="🔙 Menu Withdraw",
        callback_data="withdraw"
    )

    kb.adjust(1)

    await call.message.edit_text(
        (
            "✅ <b>WITHDRAW BERHASIL DIBUAT</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🆔 ID Withdraw : <code>{withdraw_id}</code>\n\n"

            f"🏦 Metode : <b>{account['method_name']}</b>\n"
            f"👤 Nama : <b>{account['account_name']}</b>\n"
            f"💳 Nomor : <code>{account['account_number']}</code>\n\n"

            f"💰 Nominal : <b>Rp {amount:,}</b>\n"
            f"💸 Fee Admin : <b>Rp {fee:,}</b>\n"
            f"📉 Total Dipotong : <b>Rp {total:,}</b>\n"
            f"💵 Sisa Saldo : <b>Rp {remaining_balance:,}</b>\n\n"

            "⏳ Status : <b>MENUNGGU PROSES ADMIN</b>\n\n"

            "Permintaan withdraw berhasil dibuat.\n"
            "Silakan tunggu hingga admin memproses permintaan Anda."
        ).replace(",", "."),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

# =========================
# ADMIN PROSES WITHDRAW
# =========================

@router.callback_query(F.data.startswith("withdraw_process:"))
async def withdraw_process(call: CallbackQuery):

    await call.answer()

    if call.from_user.id not in ADMIN_IDS:
        return await call.answer(
            "Akses ditolak.",
            show_alert=True
        )

    withdraw_id = int(call.data.split(":")[1])

    pool = await get_pool()

    try:

        async with pool.acquire() as conn:

            async with conn.transaction():

                # Lock withdraw
                wd = await conn.fetchrow(
                    """
                    SELECT *
                    FROM withdrawals
                    WHERE id=$1
                    FOR UPDATE
                    """,
                    withdraw_id
                )

                if wd is None:
                    return await call.answer(
                        "Withdraw tidak ditemukan.",
                        show_alert=True
                    )

                if wd["status"] not in ("pending", "instant_pending"):
                    return await call.answer(
                        "Withdraw sudah diproses.",
                        show_alert=True
                    )

                await conn.execute(
                    """
                    UPDATE withdrawals
                    SET
                        status='success',
                        processed_by=$2,
                        processed_at=NOW()
                    WHERE id=$1
                    """,
                    withdraw_id,
                    call.from_user.id
                )

    except Exception as e:

        print("PROCESS WD ERROR:", e)

        return await call.answer(
            "Terjadi kesalahan.",
            show_alert=True
        )

    # Hapus tombol admin
    await call.message.edit_text(
        (
            "✅ <b>WITHDRAW BERHASIL DIPROSES</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🆔 Withdraw ID : <code>{withdraw_id}</code>\n"
            f"👤 User ID : <code>{wd['seller_id']}</code>\n\n"

            f"💰 Nominal : <b>Rp {wd['amount']:,}</b>\n"
            f"💸 Fee : <b>Rp {wd['fee']:,}</b>\n\n"

            "✅ Status : <b>SUCCESS</b>"
        ).replace(",", "."),
        parse_mode="HTML"
    )

    try:

        await call.bot.send_message(
            wd["seller_id"],
            (
                "✅ <b>WITHDRAW BERHASIL DIPROSES</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                f"🆔 ID Withdraw : <code>{withdraw_id}</code>\n"
                f"💰 Nominal : <b>Rp {wd['amount']:,}</b>\n\n"

                "Dana withdraw telah berhasil diproses oleh admin.\n"
                "Silakan cek rekening tujuan Anda."
            ).replace(",", "."),
            parse_mode="HTML"
        )

    except Exception as e:
        print("NOTIF USER ERROR:", e)

    # =========================
    # POST KE CHANNEL BUKTI WD
    # =========================

    try:

        await call.bot.send_message(
            -1003894841696,
            (
                "🎉 <b>WITHDRAW BERHASIL</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                f"🆔 Withdraw ID : <code>{withdraw_id}</code>\n"
                f"👤 User ID : <code>{mask_id(wd['seller_id'])}</code>\n"

                f"🏦 Metode : <b>{wd['method']}</b>\n"
                f"👤 Nama Rekening : <b>{mask_name(wd['account_name'])}</b>\n"
                f"💳 Nomor : <code>{mask_account(wd['account_number'])}</code>\n\n"

                f"💰 Nominal : <b>Rp {wd['amount']:,}</b>\n"

                "✅ <b>Status : SUCCESS</b>"
            ).replace(",", "."),
            parse_mode="HTML"
        )

    except Exception as e:
        print("POST CHANNEL ERROR:", e)

# =========================
# ADMIN REJECT WITHDRAW
# =========================

@router.callback_query(F.data.startswith("withdraw_reject:"))
async def withdraw_reject(call: CallbackQuery):

    await call.answer()

    if call.from_user.id not in ADMIN_IDS:
        return await call.answer(
            "Akses ditolak.",
            show_alert=True
        )

    withdraw_id = int(call.data.split(":")[1])

    pool = await get_pool()

    try:

        async with pool.acquire() as conn:

            async with conn.transaction():

                # Lock withdraw
                wd = await conn.fetchrow(
                    """
                    SELECT *
                    FROM withdrawals
                    WHERE id=$1
                    FOR UPDATE
                    """,
                    withdraw_id
                )

                if wd is None:
                    return await call.answer(
                        "Withdraw tidak ditemukan.",
                        show_alert=True
                    )

                if wd["status"] not in ("pending", "instant_pending"):
                    return await call.answer(
                        "Withdraw sudah diproses.",
                        show_alert=True
                    )

                refund = wd["amount"] + wd["fee"]

                # Kembalikan saldo
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance + $1
                    WHERE telegram_id=$2
                    """,
                    refund,
                    wd["seller_id"]
                )

                # Histori saldo (opsional jika tabel ada)
                await conn.execute(
                    """
                    INSERT INTO wallet_transactions
                    (
                        telegram_id,
                        type,
                        amount,
                        description,
                        created_at
                    )
                    VALUES
                    (
                        $1,
                        'withdraw_refund',
                        $2,
                        $3,
                        NOW()
                    )
                    """,
                    wd["seller_id"],
                    refund,
                    f"Refund Withdraw #{withdraw_id}"
                )

                # Update status
                await conn.execute(
                    """
                    UPDATE withdrawals
                    SET
                        status='rejected',
                        processed_by=$2,
                        processed_at=NOW()
                    WHERE id=$1
                    """,
                    withdraw_id,
                    call.from_user.id
                )

    except Exception as e:

        print("REJECT WD ERROR:", e)

        return await call.answer(
            "Terjadi kesalahan.",
            show_alert=True
        )

    # Update pesan admin
    await call.message.edit_text(
        (
            "❌ <b>WITHDRAW DITOLAK</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🆔 Withdraw ID : <code>{withdraw_id}</code>\n"
            f"👤 User ID : <code>{wd['seller_id']}</code>\n\n"

            f"💰 Nominal : <b>Rp {wd['amount']:,}</b>\n"
            f"💸 Fee : <b>Rp {wd['fee']:,}</b>\n"
            f"💵 Refund : <b>Rp {refund:,}</b>\n\n"

            "❌ Status : <b>REJECTED</b>\n"
            "Saldo telah dikembalikan."
        ).replace(",", "."),
        parse_mode="HTML"
    )

    # Notifikasi user
    try:

        await call.bot.send_message(
            wd["seller_id"],
            (
                "❌ <b>WITHDRAW DITOLAK</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                f"🆔 ID Withdraw : <code>{withdraw_id}</code>\n"
                f"💰 Nominal : <b>Rp {wd['amount']:,}</b>\n"
                f"💸 Fee : <b>Rp {wd['fee']:,}</b>\n"
                f"💵 Dana Dikembalikan : <b>Rp {refund:,}</b>\n\n"

                "Saldo withdraw telah dikembalikan ke akun Anda."
            ).replace(",", "."),
            parse_mode="HTML"
        )

    except Exception as e:
        print("NOTIF USER ERROR:", e)

@router.callback_query(F.data == "withdraw_closed")
async def withdraw_closed(call: CallbackQuery):

    await call.answer()

    kb = InlineKeyboardBuilder()
    kb.button(
        text="🔙 Menu Withdraw",
        callback_data="withdraw"
    )

    await call.message.edit_text(
        (
            "🔒 <b>Layanan Withdraw Sedang Tutup</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            "Jam Operasional\n"
            "• Senin - Jumat\n"
            "• 09:00 - 19:00 WIB\n"
            "• Sabtu & Minggu Libur\n\n"
            "Silakan kembali pada jam operasional."
        ),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == "withdraw_history")
async def withdraw_history(call: CallbackQuery):

    await call.answer()

    pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT
            id,
            amount,
            fee,
            status,
            created_at
        FROM withdrawals
        WHERE seller_id=$1
        ORDER BY id DESC
        LIMIT 10
        """,
        call.from_user.id
    )

    if not rows:

        kb = InlineKeyboardBuilder()
        kb.button(
            text="🔙 Menu Withdraw",
            callback_data="withdraw"
        )

        return await call.message.edit_text(
            "📜 <b>Belum ada riwayat withdraw.</b>",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

    status_map = {
        "pending": "⏳ Pending",
        "instant_pending": "⚡ Instant Pending",
        "success": "✅ Success",
        "rejected": "❌ Rejected"
    }

    text = "📜 <b>RIWAYAT WITHDRAW</b>\n━━━━━━━━━━━━━━\n\n"

    for row in rows:

        text += (
            f"🆔 <code>{row['id']}</code>\n"
            f"💰 Rp {row['amount']:,}\n"
            f"📌 {status_map.get(row['status'], row['status'])}\n"
            f"📅 {row['created_at'].strftime('%d-%m-%Y %H:%M')}\n\n"
        ).replace(",", ".")

    kb = InlineKeyboardBuilder()
    kb.button(
        text="🔙 Menu Withdraw",
        callback_data="withdraw"
    )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

