from aiogram.fsm.state import State, StatesGroup


class CalcForm(StatesGroup):
    gender = State()
    age = State()
    height = State()
    weight = State()
    activity = State()
    target = State()
    mode = State()
