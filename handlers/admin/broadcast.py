from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter
)

import asyncio

from database import get_pool
from config import ADMIN_IDS


router = Router()


# =========================
# CONFIG
# =========================

BATCH_SIZE = 20
BASE_DELAY = 0.1


def is_admin(user_id: int):
    return user_id in ADMIN_IDS



# =========================
# FSM
# =========================

class BroadcastState(StatesGroup):
    waiting_message = State()
    choose_target = State()
    confirm = State()



# =========================
# START BROADCAST
# =========================

@router.callback_query(F.data == "admin_broadcast")
async def start(call: CallbackQuery, state: FSMContext):

    if not is_admin(call.from_user.id):
        return await call.answer(
            "❌ Tidak punya akses",
            show_alert=True
        )


    await state.set_state(
        BroadcastState.waiting_message
    )


    await call.message.edit_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Kirim pesan yang ingin dikirim.\n\n"
        "Support:\n"
        "✅ Text\n"
        "✅ Foto\n"
        "✅ Video\n"
        "✅ Dokumen\n"
        "✅ Forward\n\n"
        "Ketik /cancel untuk batal.",
        parse_mode="HTML"
    )



# =========================
# CANCEL
# =========================

@router.message(F.text == "/cancel")
async def cancel(
    message: Message,
    state: FSMContext
):

    await state.clear()

    await message.answer(
        "❌ Broadcast dibatalkan"
    )



# =========================
# SAVE MESSAGE
# =========================

@router.message(
    BroadcastState.waiting_message
)
async def save_message(
    message: Message,
    state: FSMContext
):

    await state.update_data(
        msg=message
    )


    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Semua User",
                    callback_data="target_all"
                )
            ]
        ]
    )


    await message.answer(
        "🎯 Target:",
        reply_markup=kb
    )


    await state.set_state(
        BroadcastState.choose_target
    )



# =========================
# TARGET
# =========================

@router.callback_query(
    F.data == "target_all"
)
async def choose_target(
    call: CallbackQuery,
    state: FSMContext
):

    await state.update_data(
        target="all"
    )


    data = await state.get_data()

    msg = data["msg"]


    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Kirim",
                    callback_data="bc_send"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Batal",
                    callback_data="bc_cancel"
                )
            ]
        ]
    )


    await call.message.edit_text(
        "👀 Preview broadcast:"
    )


    await msg.copy_to(
        call.message.chat.id,
        reply_markup=kb
    )


    await state.set_state(
        BroadcastState.confirm
    )



# =========================
# GET USERS
# =========================

async def get_targets(pool):

    rows = await pool.fetch(
        """
        SELECT user_id
        FROM users
        """
    )

    return [
        {
            "chat_id": row["user_id"]
        }
        for row in rows
    ]



# =========================
# SEND ENGINE
# =========================

async def run_broadcast(
    msg: Message,
    users,
    pool,
    progress
):

    total = len(users)

    success = 0
    failed = 0
    blocked = 0


    lock = asyncio.Lock()



    async def send_one(uid):

        nonlocal success
        nonlocal failed
        nonlocal blocked


        retry = 0


        while retry < 3:

            try:

                await msg.copy_to(
                    uid,
                    protect_content=False
                )


                async with lock:
                    success += 1


                return



            except TelegramForbiddenError:


                async with lock:
                    blocked += 1


                await pool.execute(
                    """
                    DELETE FROM users
                    WHERE user_id=$1
                    """,
                    uid
                )


                return



            except TelegramRetryAfter as e:

                await asyncio.sleep(
                    e.retry_after + 1
                )

                retry += 1



            except Exception as e:

                print(
                    "Broadcast error:",
                    e
                )

                retry += 1
                await asyncio.sleep(1)



        async with lock:
            failed += 1



    for i in range(
        0,
        total,
        BATCH_SIZE
    ):


        batch = users[
            i:i+BATCH_SIZE
        ]


        await asyncio.gather(
            *[
                send_one(
                    x["chat_id"]
                )
                for x in batch
            ]
        )


        try:

            await progress.edit_text(
                "🚀 <b>Broadcast berjalan</b>\n\n"
                f"👥 Total : {total}\n"
                f"✅ Berhasil : {success}\n"
                f"🚫 Block : {blocked}\n"
                f"❌ Gagal : {failed}\n\n"
                f"Progress {min(i+BATCH_SIZE,total)}/{total}",
                parse_mode="HTML"
            )

        except:
            pass



        await asyncio.sleep(
            BASE_DELAY
        )


    return (
        total,
        success,
        failed,
        blocked
    )



# =========================
# SEND NOW
# =========================

@router.callback_query(
    F.data == "bc_send"
)
async def send_now(
    call: CallbackQuery,
    state: FSMContext
):

    if not is_admin(
        call.from_user.id
    ):
        return


    data = await state.get_data()

    msg = data["msg"]


    pool = await get_pool()


    users = await get_targets(
        pool
    )


    if not users:

        return await call.message.edit_text(
            "❌ Belum ada user"
        )


    progress = await call.message.edit_text(
        "🚀 Memulai broadcast..."
    )


    total, success, failed, blocked = await run_broadcast(
        msg,
        users,
        pool,
        progress
    )


    await state.clear()


    await progress.edit_text(
        "✅ <b>BROADCAST SELESAI</b>\n\n"
        f"👥 Total : {total}\n"
        f"✅ Terkirim : {success}\n"
        f"🚫 Block : {blocked}\n"
        f"❌ Gagal : {failed}",
        parse_mode="HTML"
    )



# =========================
# CANCEL BUTTON
# =========================

@router.callback_query(
    F.data == "bc_cancel"
)
async def cancel_btn(
    call: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    await call.message.edit_text(
        "❌ Broadcast dibatalkan"
    )
