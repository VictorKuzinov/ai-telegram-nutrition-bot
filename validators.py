from aiogram.types import Message

async def validate_age(message: Message) -> int|None:
    try:
        age = int(message.text)
    except ValueError:
        await message.answer("Возраст должен быть числом.")
        return None
    if age < 5 or age > 120:
        await message.answer(
            "Введите корректный возраст."
        )
        return None
    return age


async def validate_height(message: Message) -> int|None:
    try:
        height = int(message.text)
    except ValueError:
        await message.answer("Рост должен быть числом.")
        return None
    if height < 50 or height > 300:
        await message.answer(
            "Введите корректный рост."
        )
        return None
    return height


async def validate_weight(message: Message) -> float|None:
    try:
        weight = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Вес должен быть числом.")
        return None
    if weight < 20 or weight > 500:
        await message.answer(
            "Введите корректный вес."
        )
        return None
    return weight