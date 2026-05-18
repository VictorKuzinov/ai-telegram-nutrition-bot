from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from states import CalcForm

from db.repositories import (
    get_user_profile,
    create_user_profile,
    update_user_profile,
)
from keyboards import (
    gender_keyboard,
    activity_keyboard,
    target_keyboard, calc_menu_keyboard,
    main_menu_keyboard,
)
from services.message_builder import (
    build_calc_result_message,
    calculate_profile_results,
)
from validators import (
    validate_age,
    validate_height,
    validate_weight,
)

router = Router()

@router.message(F.text == "📊 Расчёты")
async def calc_menu_handler(
    message: Message,
) -> None:
    await message.answer(
        f"Выберите действие:",
        reply_markup=calc_menu_keyboard,
    )

@router.message(F.text == "📊 Рассчитать БЖУ")
async def calc_from_menu_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await start_calc_flow(message, state, mode="create")

@router.message(F.text == "🔄 Пересчитать")
async def recalc_from_menu_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await start_calc_flow(
        message,
        state,
        mode="update",
    )

@router.message(F.text == "⬅️ Назад")
async def back_to_main_menu_handler(
    message: Message,
) -> None:

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard,
    )

async def start_calc_flow(
        message: Message,
        state: FSMContext,
        mode: str,
) -> None:
    telegram_id = message.from_user.id
    await state.update_data(mode=mode)
    profile = get_user_profile(telegram_id)
    if mode == "create" and profile is not None:
        results = calculate_profile_results(profile)
        await message.answer(
            build_calc_result_message(
                profile, results
            )
        )
        return

    await state.set_state(CalcForm.gender)
    await message.answer(
        "Выберите пол:",
        reply_markup=gender_keyboard
    )

@router.message(Command('calc'))
async def calc_handler(
        message: Message,
        state: FSMContext
)-> None:

    await start_calc_flow(
        message,
        state,
        mode="create"
    )

@router.message(Command('recalc'))
async def recalc_handler(
    message: Message,
    state: FSMContext,
) -> None:

    await start_calc_flow(
        message,
        state,
        mode="update",
    )

@router.callback_query(
    CalcForm.gender,
    F.data.startswith("gender:")
)
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

    profile_data = {
        "telegram_id": callback.from_user.id,
        "full_name": callback.from_user.full_name,
        "gender": data["gender"],
        "age": data["age"],
        "height": data["height"],
        "weight": data["weight"],
        "activity": data["activity"],
        "target": data["target"],
    }

    if data["mode"] == "create":
        profile = get_user_profile(callback.from_user.id)

        if profile is None:
            profile = create_user_profile(profile_data)
    elif  data["mode"] == "update":
        profile = update_user_profile(
            telegram_id=callback.from_user.id,
            updates=profile_data)
    else:
        await callback.message.answer("Неизвестный режим расчёта.")
        await state.clear()
        await callback.answer()
        return

    if profile is None:
        await callback.message.answer("Профиль не найден.")
        await state.clear()
        await callback.answer()
        return

    results = calculate_profile_results(profile)

    await callback.message.answer(
        build_calc_result_message(
            profile=profile,
            results=results
        ),
        reply_markup=calc_menu_keyboard
    )
    await state.clear()
    await callback.answer()