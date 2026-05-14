from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

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

# "🪑 Сижу почти весь день"
# "🚶 Хожу / лёгкие тренировки"
# "🏃 Тренировки 3-5 раз в неделю"
# "🏋️ Интенсивные тренировки"
# "🔥 Спорт или тяжёлый физический труд"

target_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Похудение", callback_data="target:loss")],
        [InlineKeyboardButton(text="Поддержание", callback_data="target:maintain")],
        [InlineKeyboardButton(text="Набор массы", callback_data="target:gain")],
    ]
)