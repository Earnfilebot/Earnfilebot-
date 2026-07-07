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


def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# AUTO SPEED
# =========================
def get_auto_settings(total_users: int):
    if total_users < 1000:
        return 15, 0.03
    elif total_users < 3000:
        return 12, 0.04
    elif total_users < 7000:
        return 8, 0.05
    else:
        return 5, 0.07


# =========================
# DB SETTINGS HELPER
# =========================
async def get_setting(pool, key, default=None):
    val = await pool.fetchval("SELECT value FROM settings WHERE key=$1", key)
    return val if val is not None else default


async def set_setting(pool, key, value):
    await pool.execute("""
        INSERT INTO settings(key, value)
        VALUES($1, $2)
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value
    """, key, str(value))


# =========================
# FSM
# =========================
class BroadcastState(StatesGroup):
    waiting_message = State()
    confirm = State()


class SchedulerState(StatesGroup):
    waiting_time = State()
    waiting_text = State()


# =========================
# ADMIN PANEL
# =========================
@router.callback_query(F.data == "admin_settings")
async def admin_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🛠 Maintenance", callback_data="set_maintenance")],
        [InlineKeyboardButton(text="⏰ Scheduler", callback_data="set_scheduler")],
        [InlineKeyboardButton(text="⚡ Auto Speed Info", callback_data="speed_info")]
    ])

    await call.message.edit_text(
        "⚙️ <b>ADMIN PANEL</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )


# =========================
# MAINTENANCE
# =========================
@router.callback_query(F.data == "set_maintenance")
async def maintenance_menu(call: CallbackQuery):
    pool = await get_pool()
    status = await get_setting(pool, "maintenance", "off")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ON' if status=='on' else '❌ OFF'}",
            callback_data="toggle_maintenance"
        )]
    ])

    await call.message.edit_text(
        f"🛠 Maintenance Mode\n\nStatus: <b>{status.upper()}</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance(call: CallbackQuery):
    pool = await get_pool()
    current = await get_setting(pool, "maintenance", "off")

    new = "off" if current == "on" else "on"
    await set_setting(pool, "maintenance", new)

    await call.answer(f"Maintenance: {new.upper()}")
    await maintenance_menu(call)


# =========================
# BLOCK USER IF MAINTENANCE
# =========================
async def is_maintenance():
    pool = await get_pool()
    return await get_setting(pool, "maintenance", "off") == "on"


# =========================
# SCHEDULER MENU
# =========================
@router.callback_query(F.data == "set_scheduler")
async def scheduler_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Set Jam", callback_data="set_time")],
        [InlineKeyboardButton(text="Set Pesan", callback_data="set_text")],
        [InlineKeyboardButton(text="ON/OFF", callback_data="toggle_scheduler")]
    ])

    await call.message.edit_text("⏰ Scheduler", reply_markup=kb)


@router.callback_query(F.data == "set_time")
async def input_time(call: CallbackQuery, state: FSMContext):
    await state.set_state(SchedulerState.waiting_time)
    await call.message.answer("Masukkan jam (HH:MM)")


@router.message(SchedulerState.waiting_time)
async def save_time(message: Message, state: FSMContext):
    pool = await get_pool()
    await set_setting(pool, "schedule_time", message.text)
    await message.answer("✅ Jam disimpan")
    await state.clear()


@router.callback_query(F.data == "set_text")
async def input_text(call: CallbackQuery, state: FSMContext):
    await state.set_state(SchedulerState.waiting_text)
    await call.message.answer("Kirim pesan scheduler")


@router.message(SchedulerState.waiting_text)
async def save_text(message: Message, state: FSMContext):
    pool = await get_pool()
    await set_setting(pool, "schedule_text", message.text)
    await message.answer("✅ Pesan disimpan")
    await state.clear()


@router.callback_query(F.data == "toggle_scheduler")
async def toggle_scheduler(call: CallbackQuery):
    pool = await get_pool()
    current = await get_setting(pool, "scheduler", "off")

    new = "off" if current == "on" else "on"
    await set_setting(pool, "scheduler", new)

    await call.answer(f"Scheduler: {new}")


# =========================
# AUTO SPEED INFO
# =========================
@router.callback_query(F.data == "speed_info")
async def speed_info(call: CallbackQuery):
    pool = await get_pool()
    total = await pool.fetchval("SELECT COUNT(*) FROM users")

    mc, delay = get_auto_settings(total)

    await call.message.edit_text(
        f"⚡ AUTO SPEED\n\n👥 {total}\n🔥 {mc}\n⏱ {delay}"
    )


# =========================
# BROADCAST START
# =========================
@router.callback_query(F.data == "admin_broadcast")
async def start_bc(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    await state.set_state(BroadcastState.waiting_message)
    await call.message.edit_text("Kirim pesan broadcast")


@router.message(BroadcastState.waiting_message)
async def preview(message: Message, state: FSMContext):
    await state.update_data(msg=message)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kirim", callback_data="bc_send")],
        [InlineKeyboardButton(text="Batal", callback_data="bc_cancel")]
    ])

    await message.copy_to(message.chat.id, reply_markup=kb)
    await state.set_state(BroadcastState.confirm)


# =========================
# SEND SAFE
# =========================
async def send_safe(bot, msg, user_id):
    try:
        await msg.copy_to(user_id)
        return "ok"
    except TelegramForbiddenError:
        return "blocked"
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        return "retry"
    except:
        return "fail"


# =========================
# BROADCAST ENGINE
# =========================
async def run_broadcast(bot, msg, users, pool, progress):
    total = len(users)

    MAX_CONCURRENT, BASE_DELAY = get_auto_settings(total)

    success = failed = blocked = 0
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    delay = BASE_DELAY

    async def worker(user):
        nonlocal success, failed, blocked, delay

        async with sem:
            r = await send_safe(bot, msg, user["user_id"])

            if r == "ok":
                success += 1
            elif r == "blocked":
                blocked += 1
                await pool.execute("DELETE FROM users WHERE user_id=$1", user["user_id"])
            else:
                failed += 1
                delay += 0.01

            await asyncio.sleep(delay)

    tasks = [asyncio.create_task(worker(u)) for u in users]
    await asyncio.gather(*tasks)

    return total, success, failed, blocked


@router.callback_query(F.data == "bc_send")
async def send_bc(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    msg = data["msg"]

    pool = await get_pool()
    users = await pool.fetch("SELECT user_id FROM users")

    progress = await call.message.edit_text("🚀 Sending...")

    total, success, failed, blocked = await run_broadcast(
        bot, msg, users, pool, progress
    )

    await state.clear()

    await progress.edit_text(
        f"✅ DONE\n👥 {total}\n✅ {success}\n❌ {failed}\n🚫 {blocked}"
    )


@router.callback_query(F.data == "bc_cancel")
async def cancel_bc(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Dibatalkan")


# =========================
# SCHEDULER LOOP
# =========================
async def scheduler_loop(bot: Bot):
    while True:
        pool = await get_pool()

        enabled = await get_setting(pool, "scheduler", "off")
        time_set = await get_setting(pool, "schedule_time", "09:00")
        text = await get_setting(pool, "schedule_text", "Halo!")

        now = datetime.now().strftime("%H:%M")

        if enabled == "on" and now == time_set:
            users = await pool.fetch("SELECT user_id FROM users")

            for user in users:
                try:
                    await bot.send_message(user["user_id"], text)
                    await asyncio.sleep(0.05)
                except:
                    pass

            await asyncio.sleep(60)

        await asyncio.sleep(10)
