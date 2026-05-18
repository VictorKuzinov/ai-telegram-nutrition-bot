from aiogram import Router, F
from aiogram.types import Message

from keyboards import ai_menu_keyboard

router = Router()

@router.message(F.text == "🤖 AI функции")
async def ai_menu_handler(
    message: Message,
) -> None:
    await message.answer(
        f"Выберите действие:",
        reply_markup=ai_menu_keyboard,
    )
