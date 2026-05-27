from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

gender_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Мужчина", callback_data="gender:M"),
            InlineKeyboardButton(text="Женщина", callback_data="gender:F"),
        ]
    ]
)

activity_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🪑 Сижу почти весь день", callback_data="activity:sedentary")],
        [InlineKeyboardButton(text="🚶 Хожу / лёгкие тренировки", callback_data="activity:light")],
        [InlineKeyboardButton(text="🏃 Тренировки 3-5 раз в неделю", callback_data="activity:moderate")],
        [InlineKeyboardButton(text="🏋️ Интенсивные тренировки", callback_data="activity:high")],
        [InlineKeyboardButton(text="🔥 Спорт или тяжёлый физический труд", callback_data="activity:extreme")],
    ]
)

target_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Похудение", callback_data="target:loss")],
        [InlineKeyboardButton(text="Поддержание", callback_data="target:maintain")],
        [InlineKeyboardButton(text="Набор массы", callback_data="target:gain")],
    ]
)

start_calc_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать расчёт",callback_data="start_calc")],
    ]
)

main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Расчёты"),
            KeyboardButton(text="🤖 AI функции"),
        ],
        [
            KeyboardButton(text="👤 Профиль"),
            KeyboardButton(text="📖 Дневник"),

        ],
    ],
    resize_keyboard=True,
)

calc_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Рассчитать БЖУ"),
            KeyboardButton(text="🔄 Пересчитать"),
            KeyboardButton(text="⬅️ Назад"),
        ],
    ],
    resize_keyboard=True,
)

ai_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📷 Распознать блюдо"),
            KeyboardButton(text="🍲 Создать рецепт"),
        ],
        [
            KeyboardButton(text="📋 Меню на день"),
            KeyboardButton(text="⬅️ Назад"),
        ],
    ],
    resize_keyboard=True,
)

confirm_food_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да",
                callback_data="confirm_food_yes",
            ),
            InlineKeyboardButton(
                text="✏️ Правка",
                callback_data="confirm_food_no",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="confirm_food_cancel",
            ),
        ],
    ]
)

diary_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🍽 Сегодня"),
            KeyboardButton(text="🔥 Остаток"),
        ],
        [
            KeyboardButton(text="📅 История"),
            KeyboardButton(text="⬅️ Назад"),
        ],
    ],
    resize_keyboard=True,
)

profile_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="✏️ Изменить профиль"),
            KeyboardButton(text="🎯 Изменить цель"),
        ],
        [
            KeyboardButton(text="⚖ Обновить вес"),
            KeyboardButton(text="⬅️ Назад"),
        ],
    ],
    resize_keyboard=True,
)