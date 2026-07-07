from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from datetime import datetime
import asyncio

from database import get_pool
from handlers.admin.admins import is_admin


router = Router()


# =========================
# DB SETTINGS
# =========================

async def get_setting(pool, key, default=None):
    value = await pool.fetchval(
        "SELECT value FROM settings WHERE key=$1",
        key
    )

    return value if value is not None else default



async def set_setting(pool,key,value):

    await pool.execute(
        """
        INSERT INTO settings(key,value)
        VALUES($1,$2)

        ON CONFLICT(key)
        DO UPDATE SET value=EXCLUDED.value
        """,
        key,
        str(value)
    )



# =========================
# FSM
# =========================

class AdminState(StatesGroup):

    add_admin = State()
    add_owner = State()


class SchedulerState(StatesGroup):

    waiting_time = State()
    waiting_text = State()



class MaintenanceState(StatesGroup):

    waiting_text = State()



# =========================
# MENU
# =========================

@router.callback_query(F.data=="admin_settings")
async def admin_settings(call:CallbackQuery):

    if not is_admin(call.from_user.id):
        return


    kb = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="👑 Add Owner",
                    callback_data="add_owner"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🛡 Add Admin",
                    callback_data="add_admin"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🛠 Maintenance",
                    callback_data="set_maintenance"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⏰ Scheduler",
                    callback_data="set_scheduler"
                )
            ],

        ]
    )


    await call.message.edit_text(
        "⚙️ <b>ADMIN PANEL</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )



# =========================
# ADD ADMIN
# =========================

@router.callback_query(F.data=="add_admin")
async def add_admin(call:CallbackQuery,state:FSMContext):

    if not is_admin(call.from_user.id):
        return


    await state.set_state(AdminState.add_admin)

    await call.message.answer(
        "🛡 Kirim Telegram ID admin baru"
    )



@router.message(AdminState.add_admin)
async def save_admin(message:Message,state:FSMContext):

    if not message.text.isdigit():

        return await message.answer(
            "❌ ID harus angka"
        )


    user_id=int(message.text)

    pool=await get_pool()


    await pool.execute(
        """
        INSERT INTO admins(user_id,role)

        VALUES($1,'admin')

        ON CONFLICT(user_id)

        DO UPDATE SET role='admin'
        """,
        user_id
    )


    await message.answer(
        f"✅ Admin ditambahkan\nID: <code>{user_id}</code>",
        parse_mode="HTML"
    )


    await state.clear()



# =========================
# ADD OWNER
# =========================

@router.callback_query(F.data=="add_owner")
async def add_owner(call:CallbackQuery,state:FSMContext):

    if not is_admin(call.from_user.id):
        return


    await state.set_state(AdminState.add_owner)

    await call.message.answer(
        "👑 Kirim Telegram ID owner baru"
    )



@router.message(AdminState.add_owner)
async def save_owner(message:Message,state:FSMContext):

    if not message.text.isdigit():

        return await message.answer(
            "❌ ID harus angka"
        )


    user_id=int(message.text)

    pool=await get_pool()


    await pool.execute(
        """
        INSERT INTO admins(user_id,role)

        VALUES($1,'owner')

        ON CONFLICT(user_id)

        DO UPDATE SET role='owner'
        """,
        user_id
    )


    await message.answer(
        f"👑 Owner ditambahkan\nID: <code>{user_id}</code>",
        parse_mode="HTML"
    )


    await state.clear()



# =========================
# MAINTENANCE
# =========================

@router.callback_query(F.data=="set_maintenance")
async def maintenance_menu(call:CallbackQuery):

    pool=await get_pool()

    status=await get_setting(
        pool,
        "maintenance",
        "off"
    )


    kb=InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="ON/OFF",
                    callback_data="toggle_maintenance"
                )
            ],

            [
                InlineKeyboardButton(
                    text="✏️ Set Pesan",
                    callback_data="set_maint_text"
                )
            ]

        ]
    )


    await call.message.edit_text(
        f"🛠 Maintenance : {status}",
        reply_markup=kb
    )



@router.callback_query(F.data=="toggle_maintenance")
async def toggle(call:CallbackQuery):

    pool=await get_pool()

    old=await get_setting(
        pool,
        "maintenance",
        "off"
    )


    new="off" if old=="on" else "on"


    await set_setting(
        pool,
        "maintenance",
        new
    )


    await call.answer(
        f"Maintenance {new}"
    )



@router.callback_query(F.data=="set_maint_text")
async def maint_text(call:CallbackQuery,state:FSMContext):

    await state.set_state(
        MaintenanceState.waiting_text
    )


    await call.message.answer(
        "Kirim pesan maintenance"
    )



@router.message(MaintenanceState.waiting_text)
async def save_maint(message:Message,state:FSMContext):

    pool=await get_pool()

    await set_setting(
        pool,
        "maintenance_text",
        message.text
    )


    await message.answer(
        "✅ Pesan disimpan"
    )


    await state.clear()



# =========================
# SCHEDULER
# =========================

@router.callback_query(F.data=="set_scheduler")
async def scheduler_menu(call:CallbackQuery):

    kb=InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🕒 Set Jam",
                    callback_data="set_time"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📝 Set Pesan",
                    callback_data="set_text"
                )
            ]

        ]
    )


    await call.message.edit_text(
        "⏰ Scheduler",
        reply_markup=kb
    )



@router.callback_query(F.data=="set_time")
async def set_time(call:CallbackQuery,state:FSMContext):

    await state.set_state(
        SchedulerState.waiting_time
    )

    await call.message.answer(
        "Format HH:MM"
    )



@router.message(SchedulerState.waiting_time)
async def save_time(message:Message,state:FSMContext):

    pool=await get_pool()

    await set_setting(
        pool,
        "schedule_time",
        message.text
    )

    await message.answer(
        "✅ Jam disimpan"
    )

    await state.clear()



@router.callback_query(F.data=="set_text")
async def set_text(call:CallbackQuery,state:FSMContext):

    await state.set_state(
        SchedulerState.waiting_text
    )

    await call.message.answer(
        "Kirim pesan scheduler"
    )



@router.message(SchedulerState.waiting_text)
async def save_text(message:Message,state:FSMContext):

    pool=await get_pool()

    await set_setting(
        pool,
        "schedule_text",
        message.text
    )

    await message.answer(
        "✅ Pesan disimpan"
    )

    await state.clear()



# =========================
# SCHEDULER WORKER
# =========================

async def scheduler_loop(bot:Bot):

    last=None

    while True:

        pool=await get_pool()


        enabled=await get_setting(
            pool,
            "scheduler",
            "off"
        )


        jam=await get_setting(
            pool,
            "schedule_time",
            "09:00"
        )


        text=await get_setting(
            pool,
            "schedule_text",
            "Halo!"
        )


        now=datetime.now().strftime("%H:%M")


        if enabled=="on" and now==jam and last!=now:

            users=await pool.fetch(
                "SELECT user_id FROM users"
            )


            for u in users:

                try:

                    await bot.send_message(
                        u["user_id"],
                        text
                    )

                    await asyncio.sleep(0.05)

                except:
                    pass


            last=now


        await asyncio.sleep(10)
