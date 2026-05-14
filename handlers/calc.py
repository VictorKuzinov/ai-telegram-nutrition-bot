from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from keyboards import (
    gender_keyboard,
    activity_keyboard,
    target_keyboard,
)
from nutrition.nutrition_calc import (
    calc_bmr,
    calc_base_calories,
    calc_energy_total,
    ACTIVITY_LEVELS,
    TARGETS, calculate_bju,
)
from states import CalcForm

from validators import (
    validate_age,
    validate_height,
    validate_weight,
)


router = Router()

@router.message(Command('calc'))
async def calc_handler(
        message: Message,
        state: FSMContext,
)-> None:

    await state.set_state(CalcForm.gender)
    await message.answer("Выберите пол: ",
    reply_markup = gender_keyboard)

@router.callback_query(CalcForm.gender, F.data.startswith("gender:"))
async def gender_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    gender = callback.data.split(":")[1]

    await state.update_data(gender=gender)

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await state.set_state(CalcForm.age)

    await callback.message.answer("Введите возраст:")
    await callback.answer()


@router.message(CalcForm.age)
async def age_handler(
        message: Message,
        state: FSMContext,
) -> None:
    age = await validate_age(message)
    if age is None:
        return
    await state.update_data(age=age)
    await state.set_state(CalcForm.height)
    await message.answer("Введите рост: ")


@router.message(CalcForm.height)
async def height_handler(
        message: Message,
        state: FSMContext,
) -> None:
    height = await validate_height(message)
    if height is None:
        return
    await state.update_data(height=height)
    await state.set_state(CalcForm.weight)
    await message.answer("Введите вес: ")


@router.message(CalcForm.weight)
async def weight_handler(
        message: Message,
        state: FSMContext,
) -> None:
    weight = await validate_weight(message)
    if weight is None:
        return
    await state.update_data(weight=weight)
    await state.set_state(CalcForm.activity)
    await message.answer(
        "Выберите вашу активность: ",
        reply_markup = activity_keyboard
    )

@router.callback_query(CalcForm.activity, F.data.startswith("activity:"))
async def activity_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    activity = callback.data.split(":")[1]
    await state.update_data(activity=activity)

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await state.set_state(CalcForm.target)

    await callback.message.answer(
        "Выберите цель:",
        reply_markup = target_keyboard)
    await callback.answer()


@router.callback_query(
    CalcForm.target,
    F.data.startswith("target:")
)
async def target_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:

    target = callback.data.split(":")[1]

    await state.update_data(target=target)

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    data = await state.get_data()

    bmr = calc_bmr(
        gender=data["gender"],
        weight=data["weight"],
        height=data["height"],
        age=data["age"],
    )

    calories = round(calc_base_calories(
        bmr,
        activity_level=data["activity"],)
    )

    total_energy = calc_energy_total(
        calories,
        target=data["target"],
    )

    bju = calculate_bju(
        weight=data["weight"],
        total_energy=total_energy,
        goal=data["target"]
    )

    gender_title = (
        "Мужчина"
        if data["gender"] == "M"
        else "Женщина"
    )

    await callback.message.answer(
        f"📊 Ваш результат:\n\n"
        f"👤 Пол: {gender_title}\n"
        f"🔥 Основной обмен: {round(bmr)} ккал\n"
        f"⚡ Суточная норма: {round(calories)} ккал\n"
        f"🎯 Цель: {TARGETS[data['target']]['title']}\n"
        f"🏃 Активность: {ACTIVITY_LEVELS[data['activity']]['title']}\n"
        f"🍽 Рекомендуемая калорийность: <b>{total_energy}</b> ккал\n\n"
        f"🥩 Белки: {bju['protein']} г\n"
        f"🧈 Жиры: {bju['fat']} г\n"
        f"🍞 Углеводы: {bju['carbs']} г"
    )

    await state.clear()
    await callback.answer()
