from aiogram import Bot

from database import db
from utils import chunk_text


async def send_chunks_to_chat(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        for chunk in chunk_text(text):
            await bot.send_message(chat_id=chat_id, text=chunk)
        return True
    except Exception:
        return False


async def broadcast_to_tournament_groups(
    bot: Bot,
    tournament_id: int,
    text: str,
) -> int:
    groups = await db.get_active_groups(tournament_id)
    sent = 0
    for group in groups:
        if await send_chunks_to_chat(bot, group["telegram_chat_id"], text):
            sent += 1
    return sent


async def broadcast_to_participants(
    bot: Bot,
    tournament_id: int,
    text: str,
) -> int:
    participants = await db.get_participants(tournament_id)
    sent = 0
    for participant in participants:
        if not participant["is_active"]:
            continue
        if await send_chunks_to_chat(bot, participant["telegram_id"], text):
            sent += 1
    return sent


async def broadcast_chunks(
    bot: Bot,
    tournament_id: int,
    text: str,
) -> tuple[int, int]:
    groups_sent = await broadcast_to_tournament_groups(bot, tournament_id, text)
    users_sent = await broadcast_to_participants(bot, tournament_id, text)
    return groups_sent, users_sent
