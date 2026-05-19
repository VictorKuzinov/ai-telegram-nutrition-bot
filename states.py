from aiogram.fsm.state import State, StatesGroup


class CalcForm(StatesGroup):
    gender = State()
    age = State()
    height = State()
    weight = State()
    activity = State()
    target = State()
    mode = State()

class PhotoForm(StatesGroup):
    waiting_photo = State()
    confirm_ingredient = State()
    edit_ingredient_name = State()
    waiting_weight = State()