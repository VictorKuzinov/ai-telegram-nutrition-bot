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
    confirm_save = State()

class RecipeForm(StatesGroup):
    waiting_recipe = State()
    waiting_persons = State()
    waiting_kcal = State()
    waiting_wishes = State()

class MenuForm(StatesGroup):
    waiting_meal_count = State()
    waiting_wishes = State()

class ProfileForm(StatesGroup):
    waiting_weight = State()

class DiaryForm(StatesGroup):
    waiting_name = State()
    waiting_weight = State()
    waiting_delete_number = State()
    waiting_edit_number = State()
    waiting_edit_name = State()
    waiting_edit_weight = State()