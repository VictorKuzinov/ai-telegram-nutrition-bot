from aiogram import Router, html, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db.repositories import get_user_profile
from handlers.calc import start_calc_flow
from keyboards import start_calc_keyboard, main_menu_keyboard
from nutrition.nutrition_calc import calc_bmr, calc_base_calories, calc_energy_total, TARGETS


router = Router()


@router.callback_query(F.data == "start_calc")
async def start_calc_callback_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await start_calc_flow(
        callback.message,
        state,
    )

    await callback.answer()


@router.message(CommandStart())
async def start_handler(
    message: Message
) -> None:
    telegram_id = message.from_user.id
    profile = get_user_profile(telegram_id)

    if profile is None:
        await message.answer(
            f"Добро пожаловать, "
            f"{html.bold(message.from_user.full_name)}!"
        )
        await message.answer(
            "Я помогу:\n"
            "• рассчитать калорийность;\n"
            "• подобрать БЖУ;\n"
            "• сохранить ваш профиль.",
            reply_markup=main_menu_keyboard,
        )

        await message.answer(
            "Для начала можно рассчитать калории и БЖУ:",
            reply_markup=start_calc_keyboard,
        )
        return

    bmr = calc_bmr(
        gender=profile.gender,
        weight=profile.weight,
        height=profile.height,
        age=profile.age,
    )

    base_calories = calc_base_calories(
        bmr,
        profile.activity,
    )

    total_energy = calc_energy_total(
        base_calories,
        profile.target,
    )

    await message.answer(
        f"С возвращением,\n"
        f"{html.bold(message.from_user.full_name)}!\n\n"
        f"Ваш профиль найден."
    )

    await message.answer(
        f"🎯 Текущая цель: "
        f"{TARGETS[profile.target]['title']}\n"
        f"🍽 Калорийность: "
        f"<b>{total_energy}</b> ккал",
        reply_markup=main_menu_keyboard,
    )