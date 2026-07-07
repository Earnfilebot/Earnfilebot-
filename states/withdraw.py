from aiogram.fsm.state import State, StatesGroup


class WithdrawState(StatesGroup):

    method = State()

    account_number = State()

    account_name = State()

    amount = State()
