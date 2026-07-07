from aiogram.fsm.state import State, StatesGroup


class WithdrawState(StatesGroup):

    # =========================
    # SET REKENING / E-WALLET
    # =========================
    select_method = State()
    input_account_number = State()
    input_account_name = State()

    # =========================
    # WITHDRAW REGULER
    # =========================
    select_account = State()
    input_amount = State()
    confirm = State()

    # =========================
    # WITHDRAW INSTANT
    # =========================
    instant_select_account = State()
    instant_confirm = State()
