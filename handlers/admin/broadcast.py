from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

import asyncio
from datetime import datetime

from database import get_pool

router = Router()

# =========================
# CONFIG
# =========================
ADMIN_IDS = {6847035364}

MAX_CONCURRENT = 15
BASE_DELAY = 0.03


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================
# FSM
# =========================
class BroadcastState(StatesGroup):
    waiting_message = State()
    choose_target = State()
    confirm = State()


# =========================
# START
# =========================
@router.callback_query(F.data == "admin_broadcast")
async def start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ No access", show_alert=True)

    await state.set_state(BroadcastState.waiting_message)

    await call.message.edit_text(
        "📢 <b>BROADCAST PRO+</b>\n\n"
        "Kirim pesan untuk broadcast.\n\n"
        "Support semua tipe (text/media/forward).\n"
        "Ketik /cancel untuk batal.",
        parse_mode="HTML"
    )


# =========================
# CANCEL
# =========================
@router.message(F.text == "/cancel")
async def cancel(message: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
        await message.answer("❌ Broadcast dibatalkan.")


# =========================
# STEP 1: SIMPAN PESAN
# =========================
@router.message(BroadcastState.waiting_message)
async def save_message(message: Message, state: FSMContext):
    await state.update_data(msg=message)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 User", callback_data="target_user")],
        [InlineKeyboardButton(text="👥 Group", callback_data="target_group")],
        [InlineKeyboardButton(text="📢 Channel", callback_data="target_channel")],
        [InlineKeyboardButton(text="🌍 Semua", callback_data="target_all")],
    ])

    await message.answer("🎯 Pilih target broadcast:", reply_markup=kb)

    await state.set_state(BroadcastState.choose_target)


# =========================
# STEP 2: PILIH TARGET
# =========================
@router.callback_query(F.data.startswith("target_"))
async def choose_target(call: CallbackQuery, state: FSMContext):
    target = call.data.split("_")[1]

    await state.update_data(target=target)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Kirim Sekarang", callback_data="bc_send")],
        [InlineKeyboardButton(text="⏳ Delay 1 Menit", callback_data="bc_delay")],
        [InlineKeyboardButton(text="❌ Batal", callback_data="bc_cancel")]
    ])

    await call.message.edit_text("👀 Preview broadcast:")
    data = await state.get_data()
    msg: Message = data["msg"]

    await msg.copy_to(call.message.chat.id, reply_markup=kb)

    await state.set_state(BroadcastState.confirm)


# =========================
# SEND SAFE
# =========================
async def send_safe(msg: Message, chat_id: int):
    try:
        await msg.copy_to(chat_id)
        return "ok"

    except TelegramForbiddenError:
        return "blocked"

    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        return "retry"

    except:
        return "fail"


# =========================
# CORE ENGINE (SAFE VERSION)
# =========================
async def run_broadcast(msg: Message, chats, pool, progress_msg):
    total = len(chats)

    success = 0
    failed = 0
    blocked = 0

    lock = asyncio.Lock()

    BATCH_SIZE = 30  # kirim per gelombang
    dynamic_delay = BASE_DELAY

    async def send_with_retry(chat_id: int):
        retries = 0

        while retries < 3:
            try:
                await msg.copy_to(chat_id)
                return "ok"

            except TelegramForbiddenError:
                return "blocked"

            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 0.5)
                retries += 1

            except:
                retries += 1
                await asyncio.sleep(0.5)

        return "fail"

    for i in range(0, total, BATCH_SIZE):
        batch = chats[i:i + BATCH_SIZE]

        tasks = []
        for chat in batch:
            cid = chat["chat_id"]

            async def worker(c=cid):
                nonlocal success, failed, blocked, dynamic_delay

                result = await send_with_retry(c)

                async with lock:
                    if result == "ok":
                        success += 1

                    elif result == "blocked":
                        blocked += 1
                        await pool.execute(
                            "DELETE FROM chats WHERE chat_id=$1", c
                        )

                    else:
                        failed += 1
                        dynamic_delay += 0.005  # pelan otomatis

            tasks.append(worker())

        await asyncio.gather(*tasks)

        # update progress tiap batch
        try:
            await progress_msg.edit_text(
                f"🚀 Broadcasting...\n\n"
                f"👥 {total}\n"
                f"✅ {success} | ❌ {failed} | 🚫 {blocked}\n"
                f"⚡ Delay: {round(dynamic_delay,3)}\n\n"
                f"{min(i + BATCH_SIZE, total)}/{total}"
            )
        except:
            pass

        # jeda antar batch (WAJIB biar aman)
        await asyncio.sleep(dynamic_delay + 0.2)

    return total, success, failed, blocked


# =========================
# GET TARGET DATA
# =========================
async def get_targets(pool, target: str):
    if target == "user":
        return await pool.fetch("SELECT chat_id FROM chats WHERE type='private'")

    elif target == "group":
        return await pool.fetch("SELECT chat_id FROM chats WHERE type IN ('group','supergroup')")

    elif target == "channel":
        return await pool.fetch("SELECT chat_id FROM chats WHERE type='channel'")

    else:
        return await pool.fetch("SELECT chat_id FROM chats")


# =========================
# SEND NOW
# =========================
@router.callback_query(F.data == "bc_send")
async def send_now(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    data = await state.get_data()
    msg: Message = data["msg"]
    target = data["target"]

    pool = await get_pool()
    chats = await get_targets(pool, target)

    progress = await call.message.edit_text("🚀 Starting broadcast...")

    total, success, failed, blocked = await run_broadcast(
        msg, chats, pool, progress
    )

    await state.clear()

    await progress.edit_text(
        "✅ <b>SELESAI</b>\n\n"
        f"👥 {total}\n"
        f"✅ {success}\n"
        f"❌ {failed}\n"
        f"🚫 {blocked}",
        parse_mode="HTML"
    )


# =========================
# DELAY SEND
# =========================
@router.callback_query(F.data == "bc_delay")
async def delay_send(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    await call.message.edit_text("⏳ Mengirim dalam 1 menit...")
    await asyncio.sleep(60)

    data = await state.get_data()
    msg: Message = data["msg"]
    target = data["target"]

    pool = await get_pool()
    chats = await get_targets(pool, target)

    progress = await call.message.answer("🚀 Broadcast dimulai...")

    total, success, failed, blocked = await run_broadcast(
        msg, chats, pool, progress
    )

    await state.clear()

    await progress.edit_text(
        "✅ <b>SELESAI (DELAY)</b>\n\n"
        f"👥 {total}\n"
        f"✅ {success}\n"
        f"❌ {failed}\n"
        f"🚫 {blocked}",
        parse_mode="HTML"
    )


# =========================
# CANCEL BTN
# =========================
@router.callback_query(F.data == "bc_cancel")
async def cancel_btn(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Broadcast dibatalkan.")
