import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from config import ADMIN_IDS

from handlers.withdraw.utils import (
    withdraw_is_open,
    rupiah,
    WITHDRAW_FEE,
    INSTANT_AMOUNT,
    INSTANT_FEE,
)


router = Router()

logger = logging.getLogger(__name__)


# =========================
# KONFIRMASI WITHDRAW REGULER
# =========================

@router.callback_query(
    F.data.startswith("withdraw_confirm:")
)
async def withdraw_confirm(
    call: CallbackQuery
):

    await call.answer()


    if not withdraw_is_open():

        return await call.answer(
            "Withdraw sedang tutup.",
            show_alert=True
        )


    amount = int(
        call.data.split(":")[1]
    )


    pool = await get_pool()


    try:

        async with pool.acquire() as conn:

            async with conn.transaction():


                # =====================
                # LOCK USER
                # =====================

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



                # =====================
                # CEK PENDING
                # =====================

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

                    return await call.answer(
                        "Masih ada withdraw pending.",
                        show_alert=True
                    )



                # =====================
                # REKENING DEFAULT
                # =====================

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
                        "Rekening belum tersedia.",
                        show_alert=True
                    )



                # =====================
                # POTONG SALDO
                # =====================

                await conn.execute(
                    """
                    UPDATE users

                    SET balance =
                    balance - $1

                    WHERE telegram_id=$2
                    """,
                    total,
                    call.from_user.id
                )



                # =====================
                # INSERT WITHDRAW
                # =====================

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
                    WITHDRAW_FEE,
                    account["method_name"],
                    account["account_name"],
                    account["account_number"]
                )



                # =====================
                # HISTORY SALDO
                # =====================

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

        logger.exception(
            "WITHDRAW REGULER ERROR"
        )

        return await call.answer(
            "Terjadi kesalahan sistem.",
            show_alert=True
        )



    # =====================
    # NOTIF ADMIN
    # =====================

    await send_admin_notification(
        call,
        withdraw_id,
        amount,
        WITHDRAW_FEE,
        "pending"
    )


    # =====================
    # USER SUCCESS
    # =====================


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
            f"💸 Fee Telegram : <b>{rupiah(WITHDRAW_FEE)}</b>\n"
            f"📉 Dipotong : <b>{rupiah(amount + WITHDRAW_FEE)}</b>\n\n"

            "⏳ Status : MENUNGGU ADMIN"
        ),

        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )



# =========================
# WITHDRAW INSTANT
# =========================

@router.callback_query(
    F.data == "withdraw_instant_confirm"
)
async def withdraw_instant_confirm(
    call: CallbackQuery
):

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


                total = (
                    INSTANT_AMOUNT
                    +
                    INSTANT_FEE
                )


                if user["balance"] < total:

                    return await call.answer(
                        "Saldo tidak cukup.",
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

                    ON wm.id=uwa.method_id


                    WHERE uwa.user_id=$1

                    AND uwa.is_default=true

                    LIMIT 1

                    """,
                    call.from_user.id
                )



                if not account:

                    return await call.answer(
                        "Rekening belum ada.",
                        show_alert=True
                    )



                await conn.execute(
                    """
                    UPDATE users

                    SET balance =
                    balance-$1

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
                    INSTANT_AMOUNT,
                    INSTANT_FEE,
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



    except Exception:

        logger.exception(
            "WITHDRAW INSTANT ERROR"
        )

        return await call.answer(
            "Terjadi error.",
            show_alert=True
        )



    await send_admin_notification(
        call,
        withdraw_id,
        INSTANT_AMOUNT,
        INSTANT_FEE,
        "instant_pending"
    )



    await call.message.edit_text(

        (
            "⚡ <b>WITHDRAW INSTANT BERHASIL</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🆔 ID : <code>{withdraw_id}</code>\n"

            f"💰 Nominal : {rupiah(INSTANT_AMOUNT)}\n"
            f"💸 Fee Telegram Fast : {rupiah(INSTANT_FEE)}\n\n"

            "⚡ Prioritas admin."
        ),

        parse_mode="HTML"
    )



# =========================
# ADMIN NOTIF
# =========================

async def send_admin_notification(
    call,
    withdraw_id,
    amount,
    fee,
    status
):

    for admin_id in ADMIN_IDS:

        try:

            await call.bot.send_message(

                admin_id,

                (
                    "🚨 <b>REQUEST WITHDRAW</b>\n"
                    "━━━━━━━━━━━━━━\n\n"

                    f"🆔 ID : <code>{withdraw_id}</code>\n"
                    f"👤 User : <code>{call.from_user.id}</code>\n\n"

                    f"💰 Nominal : {rupiah(amount)}\n"
                    f"💸 Fee : {rupiah(fee)}\n"

                    f"📌 Status : {status}"
                ),

                parse_mode="HTML"
            )


        except Exception:

            logger.exception(
                "ADMIN NOTIFY ERROR"
            )
