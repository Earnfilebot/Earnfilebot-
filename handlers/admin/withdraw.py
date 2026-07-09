import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_pool
from config import ADMIN_IDS

from handlers.withdraw.utils import rupiah


router = Router()

logger = logging.getLogger(__name__)


# =====================================================
# ADMIN BUTTON
# =====================================================

@router.callback_query(
    F.data.startswith("admin_wd:")
)
async def admin_withdraw_action(
    call: CallbackQuery
):

    if call.from_user.id not in ADMIN_IDS:
        return await call.answer(
            "Tidak memiliki akses.",
            show_alert=True
        )


    data = call.data.split(":")

    action = data[1]
    withdraw_id = int(data[2])


    if action == "approve":

        await approve_withdraw(
            call,
            withdraw_id
        )


    elif action == "reject":

        await reject_menu(
            call,
            withdraw_id
        )


    await call.answer()



# =====================================================
# APPROVE
# =====================================================

async def approve_withdraw(
    call,
    withdraw_id
):

    pool = await get_pool()


    async with pool.acquire() as conn:

        withdraw = await conn.fetchrow(
            """
            SELECT
                seller_id,
                amount,
                fee,
                channel_message_id

            FROM withdraws

            WHERE id=$1
            AND status IN(
                'pending',
                'instant_pending'
            )

            """,
            withdraw_id
        )


        if not withdraw:

            return await call.answer(
                "Withdraw sudah diproses.",
                show_alert=True
            )



        await conn.execute(
            """
            UPDATE withdraws

            SET status='success',
            processed_at=NOW()

            WHERE id=$1
            """,
            withdraw_id
        )



    # UPDATE CHANNEL

    try:

        await call.bot.edit_message_text(

            chat_id=-1003894841696,

            message_id=withdraw["channel_message_id"],

            text=(

                "✅ <b>WITHDRAW SUCCESS</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                f"🆔 ID : <code>{withdraw_id}</code>\n"

                f"💰 Nominal : "
                f"<b>{rupiah(withdraw['amount'])}</b>\n\n"

                "📌 Status : SUCCESS\n\n"

                "Pembayaran sudah dilakukan."
            ),

            parse_mode="HTML"

        )


    except Exception:

        logger.exception(
            "UPDATE CHANNEL SUCCESS ERROR"
        )



    # USER NOTIF


    await call.bot.send_message(

        withdraw["seller_id"],

        (
            "✅ <b>WITHDRAW BERHASIL</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🆔 ID : <code>{withdraw_id}</code>\n"

            f"💰 Nominal : "
            f"<b>{rupiah(withdraw['amount'])}</b>\n\n"

            "Dana sudah dikirim."
        ),

        parse_mode="HTML"

    )


    await call.message.edit_reply_markup(
        reply_markup=None
    )





# =====================================================
# REJECT MENU
# =====================================================

async def reject_menu(
    call,
    withdraw_id
):


    kb = InlineKeyboardBuilder()


    reasons = [

        (
            "❌ Nomor E-Wallet Salah",
            "nomor salah"
        ),

        (
            "❌ Nama Tidak Sesuai",
            "nama tidak sesuai"
        ),

        (
            "❌ Rekening Tidak Aktif",
            "rekening tidak aktif"
        ),

        (
            "❌ Alasan Lain",
            "lain"
        )

    ]


    for text, reason in reasons:

        kb.button(

            text=text,

            callback_data=f"wd_reject:{withdraw_id}:{reason}"

        )


    kb.button(
        text="🔙 Batal",
        callback_data="wd_cancel"
    )


    kb.adjust(1)



    await call.message.edit_text(

        (
            "❌ <b>ALASAN REJECT WITHDRAW</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            "Pilih alasan:"
        ),

        parse_mode="HTML",

        reply_markup=kb.as_markup()

    )




# =====================================================
# REJECT PROCESS
# =====================================================

@router.callback_query(
    F.data.startswith("wd_reject:")
)
async def process_reject(
    call: CallbackQuery
):


    if call.from_user.id not in ADMIN_IDS:
        return await call.answer(
            "Tidak memiliki akses.",
            show_alert=True
        )


    data = call.data.split(":")


    withdraw_id = int(data[1])

    reason = data[2]


    pool = await get_pool()


    async with pool.acquire() as conn:

        async with conn.transaction():


            withdraw = await conn.fetchrow(

                """
                SELECT

                    seller_id,
                    amount,
                    fee,
                    channel_message_id

                FROM withdraws

                WHERE id=$1

                AND status IN(
                    'pending',
                    'instant_pending'
                )

                FOR UPDATE

                """,

                withdraw_id

            )


            if not withdraw:

                return await call.answer(
                    "Sudah diproses.",
                    show_alert=True
                )



            total = (
                withdraw["amount"]
                +
                withdraw["fee"]
            )


            # KEMBALIKAN SALDO


            await conn.execute(

                """
                UPDATE users

                SET balance =
                balance + $1

                WHERE telegram_id=$2

                """,

                total,

                withdraw["seller_id"]

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
                    'withdraw_refund',
                    $2,
                    $3,
                    NOW()
                )

                """,

                withdraw["seller_id"],

                total,

                f"Refund Withdraw #{withdraw_id}"

            )



            await conn.execute(

                """
                UPDATE withdraws

                SET

                status='rejected',

                reject_reason=$1,

                processed_at=NOW()

                WHERE id=$2

                """,

                reason,

                withdraw_id

            )




    # UPDATE CHANNEL


    try:

        await call.bot.edit_message_text(

            chat_id=-1003894841696,

            message_id=withdraw["channel_message_id"],

            text=(

                "❌ <b>WITHDRAW REJECTED</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                f"🆔 ID : <code>{withdraw_id}</code>\n"

                f"💰 Nominal : "
                f"<b>{rupiah(withdraw['amount'])}</b>\n\n"

                f"📌 Alasan : {reason}\n\n"

                "Saldo dikembalikan."
            ),

            parse_mode="HTML"

        )


    except Exception:

        logger.exception(
            "UPDATE CHANNEL REJECT ERROR"
        )



    # USER NOTIF


    await call.bot.send_message(

        withdraw["seller_id"],

        (

            "❌ <b>WITHDRAW DITOLAK</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"🆔 ID : <code>{withdraw_id}</code>\n"

            f"📌 Alasan : {reason}\n\n"

            f"💰 Saldo dikembalikan : "
            f"<b>{rupiah(withdraw['amount'] + withdraw['fee'])}</b>"
        ),

        parse_mode="HTML"

    )



    await call.answer(
        "Withdraw ditolak dan saldo dikembalikan."
    )



# =====================================================
# CANCEL
# =====================================================

@router.callback_query(
    F.data=="wd_cancel"
)
async def cancel_reject(
    call: CallbackQuery
):

    await call.answer()

    await call.message.delete()
