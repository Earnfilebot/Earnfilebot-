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


def back_btn():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_settings")]
    ])


# =========================
# AUTO SPEED + FLOOD DETECT
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
# DB SETTINGS
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


class MaintenanceState(StatesGroup):
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
        [InlineKeyboardButton(text="⚡ Speed Info", callback_data="speed_info")]
    ])

    await call.message.edit_text("⚙️ <b>ADMIN PANEL</b>", reply_markup=kb, parse_mode="HTML")


# =========================
# MAINTENANCE + CUSTOM MSG
# =========================
@router.callback_query(F.data == "set_maintenance")
async def maintenance_menu(call: CallbackQuery):
    pool = await get_pool()
    status = await get_setting(pool, "maintenance", "off")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'🟢 ON' if status=='on' else '🔴 OFF'}", callback_data="toggle_maintenance")],
        [InlineKeyboardButton(text="✏️ Set Pesan", callback_data="set_maint_text")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_settings")]
    ])

    await call.message.edit_text(
        f"🛠 <b>Maintenance</b>\nStatus: {status.upper()}",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance(call: CallbackQuery):
    pool = await get_pool()
    current = await get_setting(pool, "maintenance", "off")
    new = "off" if current == "on" else "on"

    await set_setting(pool, "maintenance", new)

    await call.answer(f"Maintenance {new}")
    await maintenance_menu(call)


@router.callback_query(F.data == "set_maint_text")
async def set_maint_text(call: CallbackQuery, state: FSMContext):
    await state.set_state(MaintenanceState.waiting_text)
    await call.message.answer("Kirim pesan maintenance")


@router.message(MaintenanceState.waiting_text)
async def save_maint_text(message: Message, state: FSMContext):
    pool = await get_pool()
    await set_setting(pool, "maintenance_text", message.text)

    await message.answer("✅ Pesan maintenance disimpan")
    await state.clear()


# =========================
# CHECK MAINTENANCE (PAKAI DI HANDLER USER)
# =========================
async def check_maintenance(message: Message):
    pool = await get_pool()
    status = await get_setting(pool, "maintenance", "off")

    if status == "on" and message.from_user.id not in ADMIN_IDS:
        text = await get_setting(pool, "maintenance_text", "🚧 Bot sedang maintenance")
        await message.answer(text)
        return True

    return False


# =========================
# SCHEDULER
# =========================
@router.callback_query(F.data == "set_scheduler")
async def scheduler_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Set Jam", callback_data="set_time")],
        [InlineKeyboardButton(text="📝 Set Pesan", callback_data="set_text")],
        [InlineKeyboardButton(text="🔁 ON/OFF", callback_data="toggle_scheduler")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_settings")]
    ])

    await call.message.edit_text("⏰ Scheduler", reply_markup=kb)


@router.callback_query(F.data == "set_time")
async def set_time(call: CallbackQuery, state: FSMContext):
    await state.set_state(SchedulerState.waiting_time)
    await call.message.answer("Masukkan jam HH:MM")


@router.message(SchedulerState.waiting_time)
async def save_time(message: Message, state: FSMContext):
    pool = await get_pool()
    await set_setting(pool, "schedule_time", message.text)
    await message.answer("✅ Jam disimpan")
    await state.clear()


@router.callback_query(F.data == "set_text")
async def set_text(call: CallbackQuery, state: FSMContext):
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

    await call.answer(f"Scheduler {new}")


# =========================
# SPEED INFO
# =========================
@router.callback_query(F.data == "speed_info")
async def speed_info(call: CallbackQuery):
    pool = await get_pool()
    total = await pool.fetchval("SELECT COUNT(*) FROM users")

    mc, delay = get_auto_settings(total)

    kb = back_btn()

    await call.message.edit_text(
        f"⚡ Speed\n👥 {total}\n🔥 {mc}\n⏱ {delay}",
        reply_markup=kb
    )


# =========================
# BROADCAST SAFE (ANTI FLOOD)
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


async def run_broadcast(bot, msg, users, pool):
    total = len(users)
    MAX, delay = get_auto_settings(total)

    sem = asyncio.Semaphore(MAX)
    success = failed = blocked = 0

    async def worker(u):
        nonlocal success, failed, blocked, delay

        async with sem:
            r = await send_safe(bot, msg, u["user_id"])

            if r == "ok":
                success += 1
            elif r == "blocked":
                blocked += 1
                await pool.execute("DELETE FROM users WHERE user_id=$1", u["user_id"])
            elif r == "retry":
                delay += 0.02
            else:
                failed += 1

            await asyncio.sleep(delay)

    await asyncio.gather(*[worker(u) for u in users])

    return total, success, failed, blocked


# =========================
# SCHEDULER LOOP (ANTI DOUBLE SEND)
# =========================
async def scheduler_loop(bot: Bot):
    last_sent = None

    while True:
        pool = await get_pool()

        enabled = await get_setting(pool, "scheduler", "off")
        time_set = await get_setting(pool, "schedule_time", "09:00")
        text = await get_setting(pool, "schedule_text", "Halo!")

        now = datetime.now().strftime("%H:%M")

        if enabled == "on" and now == time_set and last_sent != now:
            users = await pool.fetch("SELECT user_id FROM users")

            for u in users:
                try:
                    await bot.send_message(u["user_id"], text)
                    await asyncio.sleep(0.05)
                except:
                    pass

            last_sent = now

        await asyncio.sleep(10)
