from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from ai.gigachat_photo import get_access_token, call_gigachat_vision
from keyboards import (
    ai_menu_keyboard,
    confirm_food_keyboard,
)
from services.message_ai_parser import parse_ingredients
from states import PhotoForm

router = Router()

UPLOAD_DIR = Path("picture/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.message(F.text == "🤖 AI функции")
async def ai_menu_handler(
    message: Message,
) -> None:
    await message.answer(
        f"Выберите действие:",
        reply_markup=ai_menu_keyboard,
    )

@router.message(F.text == "📷 Распознать блюдо")
async def photo_from_menu_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(PhotoForm.waiting_photo)
    await message.answer(
        "Отправьте фото блюда. \n"
        "Можно сделать снимок камерой или выбрать "
        "изображение из галереи"
    )

@router.message(PhotoForm.waiting_photo, F.photo)
async def process_food_photo_handler(
    message: Message,
    state: FSMContext,
) -> None:

    photo = message.photo[-1]

    image_path = (
            UPLOAD_DIR /
            f"{photo.file_id}.jpg"
    )

    await message.bot.download(
        photo,
        destination=image_path,
    )
    print(image_path.exists())
    await message.answer("Фото получил, начинаю распознавание...")

    access_token = get_access_token()

    content = call_gigachat_vision(
        str(image_path),
        access_token
    )

    await message.answer(f"Распознано блюдо: {content}")
    ingredients = parse_ingredients(content)

    if not ingredients:
        await message.answer(
            "Не удалось разобрать ингредиенты. Попробуйте другое фото или введите блюдо вручную."
        )
        await state.set_state(PhotoForm.edit_ingredient_name)
        return

    await state.update_data(
        ai_ingredients=ingredients,
        ai_raw_result=content,
    )

    ingredients_text = "\n".join(
        f"• {ingredient['name']}"
        for ingredient in ingredients
    )

    await state.set_state(PhotoForm.confirm_ingredient)

    await message.answer(
        f"Я вижу:\n"
        f"{ingredients_text}\n\n"
        f"Всё верно?",
        reply_markup=confirm_food_keyboard,
    )

@router.callback_query(PhotoForm.confirm_ingredient)
async def confirm_food_handler(
        callback: CallbackQuery,
        state: FSMContext,
) -> None:
    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    if callback.data == "confirm_food_yes":
        await state.set_state(PhotoForm.waiting_weight)
        await callback.message.answer(
            "Введите общий вес порции в граммах:"
        )

    elif callback.data == "confirm_food_no":
        await state.set_state(PhotoForm.edit_ingredient_name)
        await callback.message.answer(
            "Введите блюдо или ингредиенты вручную:"
        )

    elif callback.data == "confirm_food_cancel":
        await state.clear()
        await callback.message.answer(
            "Распознавание отменено."
        )

    else:
        await callback.message.answer(
            "Пожалуйста, выберите вариант кнопкой."
        )

    await callback.answer()

@router.message(PhotoForm.waiting_weight)
async def weight_handler(
    message: Message,
    state: FSMContext,
) -> None:

    text = message.text.strip()

    if not text.isdigit():
        await message.answer(
            "Введите вес числом в граммах."
        )
        return

    weight = int(text)

    if weight <= 0:
        await message.answer(
            "Вес должен быть больше нуля."
        )
        return

    data = await state.get_data()

    ingredients = data.get("ai_ingredients", [])

    corrected_food = data.get("corrected_food")

    if corrected_food:
        food_title = corrected_food
    else:
        food_title = ", ".join(
            ingredient["name"]
            for ingredient in ingredients
        )

    await state.update_data(
        total_weight=weight,
    )

    await message.answer(
        f"✅ Блюдо сохранено:\n\n"
        f"🍽 {food_title}\n"
        f"⚖️ Вес: {weight} г"
    )

    await state.clear()

@router.message(PhotoForm.edit_ingredient_name)
async def edit_ingredient_name_handler(
    message: Message,
    state: FSMContext,
) -> None:

    text = message.text.strip()

    await state.update_data(
        corrected_food=text,
    )

    await state.set_state(
        PhotoForm.waiting_weight
    )

    await message.answer(
        "Введите вес порции в граммах:"
    )

@router.message(PhotoForm.waiting_photo)
async def wrong_photo_input_handler(
        message: Message,
) -> None:
    await message.answer(
        "Нужно отправить именно фото блюда."
    )
