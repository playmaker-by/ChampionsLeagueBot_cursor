from aiogram.types import CallbackQuery, Message

from config import ADMIN_TELEGRAM_ID
from utils import display_name


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_TELEGRAM_ID


async def reject_if_not_admin_message(message: Message) -> bool:
    if is_admin(message.from_user.id):
        return False
    return True


async def reject_if_not_admin_callback(callback: CallbackQuery) -> bool:
    if is_admin(callback.from_user.id):
        return False
    await callback.answer("⛔ Нет доступа", show_alert=True)
    return True


def format_standings(title: str, rows) -> str:
    lines = [title, ""]
    if not rows:
        lines.append("Участников пока нет.")
        return "\n".join(lines)

    for index, row in enumerate(rows, start=1):
        inactive = "" if row["is_active"] else " (неактивен)"
        lines.append(
            f"{index}. {display_name(row)} — {row['points']} "
            f"({row['exact']} точн.){inactive}"
        )

    return "\n".join(lines)
