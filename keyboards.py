from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def user_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Сделать прогноз"),
                KeyboardButton(text="📋 Мои прогнозы"),
            ],
            [
                KeyboardButton(text="🏆 Таблица"),
                KeyboardButton(text="📚 Архив"),
            ],
            [
                KeyboardButton(text="ℹ️ Правила"),
            ],
        ],
        resize_keyboard=True,
    )


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Турниры")],
            [
                KeyboardButton(text="📥 Результаты"),
                KeyboardButton(text="📊 Статистика"),
            ],
            [KeyboardButton(text="👤 Меню игрока")],
        ],
        resize_keyboard=True,
    )
