from aiogram import Router, html
from aiogram.filters import CommandStart
from aiogram.types import Message


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Это старт бота нутрициолога"
    )

    await message.answer(
        f"Добро пожаловать, "
        f"{html.bold(message.from_user.full_name)}!"
    )