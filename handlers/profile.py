from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db.repositories import get_user_profile, update_user_profile
from handlers.calc import start_calc_flow
from keyboards import profile_menu_keyboard, target_keyboard, main_menu_keyboard
from nutrition.nutrition_calc import (
    ACTIVITY_LEVELS,
    TARGETS,
    calc_bmr,
    calc_energy_total,
    calc_base_calories,
)
from states import CalcForm, ProfileForm
from validators import validate_weight

router = Router()

@router.message(F.text == "👤 Профиль")
async def profile_menu_handler(
    message: Message,
) -> None:
    await profile_follow_handler(message)

@router.message(Command('profile'))
async def profile_handler(
    message: Message,
) -> None:
    await profile_follow_handler(message)

async def profile_follow_handler(
    message: Message,
    telegram_id: int,
) -> None:
    profile = get_user_profile(telegram_id)
    if profile is None:
        await message.answer("👤 Профиль пользователя не найден.")
        return
    if profile.gender == "M":
        gender = "Мужчина"
    else:
        gender = "Женщина"

    activity_title = ACTIVITY_LEVELS.get(profile.activity)["title"]

    target_title = TARGETS.get(profile.target)["title"]

    bmr = calc_bmr(
        gender=profile.gender,
        weight=profile.weight,
        height=profile.height,
        age=profile.age,
    )

    base_calories = round(
        calc_base_calories(
            bmr,
            activity_level=profile.activity,
        )
    )

    total_energy = calc_energy_total(
        base_calories,
        target=profile.target,
    )

    answer = (
        f"👤 Профиль: {profile.full_name}\n"
        f"Пол: {gender}\n"
        f"Возраст: {profile.age} лет\n"
        f"Рост: {profile.height} см\n"
        f"Вес: {profile.weight} кг\n"
        f"🏃 Активность: {activity_title}\n"
        f"🎯 Цель: {target_title}\n\n"
        f"🔥 Дневная норма калорий: {total_energy} ккал\n"
    )
    await message.answer(answer, reply_markup=profile_menu_keyboard)

@router.message(F.text =="✏️ Изменить профиль")
async def edit_profile_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await start_calc_flow(
        message,
        state,
        mode="update",
    )

@router.message(F.text =="🎯 Изменить цель")
async def edit_target_handler(
    message: Message,
) -> None:
    await message.answer(
        "Выберите цель:",
        reply_markup=target_keyboard)

@router.callback_query(F.data.startswith("target:"))
async def target_handler(
    callback: CallbackQuery,
) -> None:

    target = callback.data.split(":")[1]

    update_user_profile(
        telegram_id=callback.from_user.id,
        updates={"target": target},
    )

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.answer("🎯 Цель обновлена")
    await profile_follow_handler(callback.message, callback.from_user.id)

@router.message(F.text == "⬅️ Назад")
async def back_to_main_menu_handler(
    message: Message,
) -> None:

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard,
    )

@router.message(F.text =="⚖ Обновить вес")
async def edit_weight_handler(
    message: Message,
    state: FSMContext
) -> None:
    await message.answer("⚖ Введите вес:")
    await state.set_state(ProfileForm.waiting_weight)

@router.message(ProfileForm.waiting_weight)
async def weight_handler(
        message: Message,
        state: FSMContext,
) -> None:
    weight = await validate_weight(message)
    if weight is None:
        return
    await state.update_data(weight=weight)
    update_user_profile(
        telegram_id=message.from_user.id,
        updates={"weight": weight},
    )

    await message.answer("⚖️ Вес обновлен")
    await profile_follow_handler(message, message.from_user.id)