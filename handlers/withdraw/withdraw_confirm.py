import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    ADMIN_IDS,
    WITHDRAW_CHANNEL_ID,
)
from database import get_pool

from handlers.withdraw.utils import (
    INSTANT_AMOUNT,
    INSTANT_FEE,
    WITHDRAW_FEE,
    rupiah,
    withdraw_is_open,
)


router = Router()

logger = logging.getLogger(__name__)


# =====================================================
# WITHDRAW REGULER CONFIRM
# =====================================================

# =====================================================
# WITHDRAW REGULER CONFIRM
# =====================================================

@router.callback_query(F.data.startswith("withdraw_confirm:"))
async def withdraw_confirm(call: CallbackQuery):

    await call.answer()

    if not withdraw_is_open():
        return await call.answer(
            "Withdraw sedang tutup.",
            show_alert=True
        )

    try:
        amount = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        return await call.answer(
            "Data withdraw tidak valid.",
            show_alert=True
        )

    pool = await get_pool()

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
                    return await call.answer(
                        "User tidak ditemukan.",
                        show_alert=True
                    )

                total = amount + WITHDRAW_FEE

                if user["balance"] < total:
                    return await call.answer(
                        "Saldo tidak cukup.",
                        show_alert=True
                    )

                pending = await conn.fetchval(
                    """
                    SELECT id
                    FROM withdraws
                    WHERE user_id=$1
                    AND status IN (
                        'pending',
                        'instant_pending'
                    )
                    LIMIT 1
                    """,
                    call.from_user.id
                )

                if pending:
                    return await call.answer(
                        "Masih ada withdraw yang sedang diproses.",
                        show_alert=True
                    )

                account = await conn.fetchrow(
                    """
                    SELECT
                        uwa.account_name,
                        uwa.account_number,
                        wm.name AS method_name

                    FROM user_withdraw_accounts uwa

                    JOIN withdraw_methods wm
                        ON wm.id = uwa.method_id

                    WHERE uwa.user_id=$1
                    AND uwa.is_default=true

                    LIMIT 1
                    """,
                    call.from_user.id
                )

                if not account:
                    return await call.answer(
                        "Silakan atur rekening tujuan terlebih dahulu.",
                        show_alert=True
                    )

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
                    INSERT INTO withdraws
                    (
                        seller_id,
                        amount,
                        method,
                        account_name,
                        account_number,
                        status,
                        fee,
                        created_at
                    )
                    VALUES
                    (
                        $1,$2,$3,$4,$5,
                        'pending',
                        $6,
                        NOW()
                    )
                    RETURNING id
                    """,
                    call.from_user.id,
                    amount,
                    account["method_name"],
                    account["account_name"],
                    account["account_number"],
                    WITHDRAW_FEE
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

    except Exception:
        logger.exception("WITHDRAW REGULER ERROR")

        return await call.answer(
            "Terjadi kesalahan sistem.",
            show_alert=True
        )

    # =========================
    # NOTIF ADMIN
    # =========================

    await send_admin_notification(
        call,
        withdraw_id,
        amount,
        WITHDRAW_FEE,
        "pending"
    )

    # =========================
    # POST CHANNEL
    # =========================

    channel_message_id = await send_withdraw_channel(
        call,
        withdraw_id,
        amount,
        WITHDRAW_FEE,
        "pending"
    )

    if channel_message_id:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE withdraws
                SET channel_message_id=$1
                WHERE id=$2
                """,
                channel_message_id,
                withdraw_id
            )

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
            "✅ <b>WITHDRAW BERHASIL DIBUAT</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            f"🆔 ID : <code>{withdraw_id}</code>\n\n"
            f"💰 Nominal : <b>{rupiah(amount)}</b>\n"
            f"💸 Fee Admin : <b>{rupiah(WITHDRAW_FEE)}</b>\n"
            f"📉 Total Potong : <b>{rupiah(total)}</b>\n\n"
            "⏳ Status : MENUNGGU ADMIN"
        ),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )

# =====================================================
# WITHDRAW INSTANT
# =====================================================

@router.callback_query(F.data == "withdraw_instant_confirm")
async def withdraw_instant_confirm(call: CallbackQuery):

    await call.answer()

    if not withdraw_is_open():
        return await call.answer(
            "Withdraw sedang tutup.",
            show_alert=True
        )

    pool = await get_pool()

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
                    return await call.answer(
                        "User tidak ditemukan.",
                        show_alert=True
                    )

                total = INSTANT_AMOUNT + INSTANT_FEE

                if user["balance"] < total:
                    return await call.answer(
                        "Saldo tidak cukup.",
                        show_alert=True
                    )

                pending = await conn.fetchval(
                    """
                    SELECT id
                    FROM withdraws
                    WHERE user_id=$1
                    AND status IN (
                        'pending',
                        'instant_pending'
                    )
                    LIMIT 1
                    """,
                    call.from_user.id
                )

                if pending:
                    return await call.answer(
                        "Masih ada withdraw yang sedang diproses.",
                        show_alert=True
                    )

                account = await conn.fetchrow(
                    """
                    SELECT
                        uwa.account_name,
                        uwa.account_number,
                        wm.name AS method_name

                    FROM user_withdraw_accounts uwa

                    JOIN withdraw_methods wm
                        ON wm.id = uwa.method_id

                    WHERE uwa.user_id=$1
                    AND uwa.is_default=true

                    LIMIT 1
                    """,
                    call.from_user.id
                )

                if not account:
                    return await call.answer(
                        "Silakan atur rekening tujuan terlebih dahulu.",
                        show_alert=True
                    )

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
                    INSERT INTO withdraws
                    (
                        user_id,
                        amount,
                        method,
                        account_name,
                        account_number,
                        status,
                        fee,
                        created_at
                    )
                    VALUES
                    (
                        $1,$2,$3,$4,$5,
                        'instant_pending',
                        $6,
                        NOW()
                    )
                    RETURNING id
                    """,
                    call.from_user.id,
                    INSTANT_AMOUNT,
                    account["method_name"],
                    account["account_name"],
                    account["account_number"],
                    INSTANT_FEE
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

    except Exception:
        logger.exception("WITHDRAW INSTANT ERROR")

        return await call.answer(
            "Terjadi kesalahan sistem.",
            show_alert=True
        )

    # =========================
    # NOTIF ADMIN
    # =========================

    await send_admin_notification(
        call,
        withdraw_id,
        INSTANT_AMOUNT,
        INSTANT_FEE,
        "instant_pending"
    )

    # =========================
    # POST CHANNEL
    # =========================

    channel_message_id = await send_withdraw_channel(
        call,
        withdraw_id,
        INSTANT_AMOUNT,
        INSTANT_FEE,
        "instant_pending"
    )

    if channel_message_id:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE withdraws
                SET channel_message_id=$1
                WHERE id=$2
                """,
                channel_message_id,
                withdraw_id
            )

    # =========================
    # USER SUCCESS
    # =========================

    await call.message.edit_text(
        (
            "⚡ <b>WITHDRAW INSTANT BERHASIL</b>\n"
            "━━━━━━━━━━━━━━\n\n"
            f"🆔 ID : <code>{withdraw_id}</code>\n\n"
            f"💰 Nominal : <b>{rupiah(INSTANT_AMOUNT)}</b>\n"
            f"💸 Fee Admin : <b>{rupiah(INSTANT_FEE)}</b>\n"
            f"📉 Total Potong : <b>{rupiah(total)}</b>\n\n"
            "⚡ Status : PRIORITAS ADMIN"
        ),
        parse_mode="HTML"
    )



# =====================================================
# ADMIN NOTIFICATION
# =====================================================

async def send_admin_notification(
    call: CallbackQuery,
    withdraw_id: int,
    amount: int,
    fee: int,
    status: str
):

    kb = InlineKeyboardBuilder()

    kb.button(
        text="✅ APPROVE",
        callback_data=f"admin_wd:approve:{withdraw_id}"
    )

    kb.button(
        text="❌ REJECT",
        callback_data=f"admin_wd:reject:{withdraw_id}"
    )

    kb.adjust(2)

    status_text = {
        "pending": "⏳ PENDING",
        "instant_pending": "⚡ INSTANT PENDING"
    }.get(status, status.upper())

    for admin_id in ADMIN_IDS:

        try:

            await call.bot.send_message(
                chat_id=admin_id,
                text=(
                    "🚨 <b>REQUEST WITHDRAW BARU</b>\n"
                    "━━━━━━━━━━━━━━\n\n"

                    f"🆔 ID : <code>{withdraw_id}</code>\n"
                    f"👤 User ID : <code>{call.from_user.id}</code>\n\n"

                    f"💰 Nominal : <b>{rupiah(amount)}</b>\n"
                    f"💸 Fee Admin : <b>{rupiah(fee)}</b>\n\n"

                    f"📌 Status : <b>{status_text}</b>"
                ),
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )

        except Exception:
            logger.exception(
                "FAILED SEND ADMIN NOTIFICATION"
            )

# =====================================================
# POST CHANNEL WITHDRAW
# =====================================================

async def send_withdraw_channel(
    call: CallbackQuery,
    withdraw_id: int,
    amount: int,
    fee: int,
    status: str
) -> int | None:

    try:

        kb = InlineKeyboardBuilder()

        kb.button(
            text="✅ APPROVE",
            callback_data=f"admin_wd:approve:{withdraw_id}"
        )

        kb.button(
            text="❌ REJECT",
            callback_data=f"admin_wd:reject:{withdraw_id}"
        )

        kb.adjust(2)

        status_text = {
            "pending": "⏳ PENDING",
            "instant_pending": "⚡ INSTANT PENDING"
        }.get(status, status.upper())

        msg = await call.bot.send_message(
            chat_id=WITHDRAW_CHANNEL_ID,
            text=(
                "💸 <b>REQUEST WITHDRAW BARU</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                f"🆔 ID : <code>{withdraw_id}</code>\n"
                f"👤 User ID : <code>{call.from_user.id}</code>\n\n"

                f"💰 Nominal : <b>{rupiah(amount)}</b>\n"
                f"💸 Fee Admin : <b>{rupiah(fee)}</b>\n\n"

                f"📌 Status : <b>{status_text}</b>\n\n"

                "Menunggu proses admin."
            ),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )

        return msg.message_id

    except TelegramBadRequest:
        logger.exception("FAILED SEND WITHDRAW CHANNEL")
        return None

    except Exception:
        logger.exception("CHANNEL WITHDRAW POST ERROR")
        return None
