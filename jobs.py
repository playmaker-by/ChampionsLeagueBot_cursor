import asyncio
import logging

from aiogram import Bot

from database import db
from utils import format_kickoff_compact, format_match_teams


logger = logging.getLogger(__name__)


async def lock_started_matches_loop(interval_seconds: int = 30):
    while True:
        try:
            closed = await db.lock_started_matches()
            if closed:
                logger.info("Закрыто матчей после стартового свистка: %s", closed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Не удалось закрыть начавшиеся матчи")
        await asyncio.sleep(interval_seconds)


async def prediction_reminder_loop(
    bot: Bot,
    interval_seconds: int = 300,
    hours: int = 2,
):
    while True:
        try:
            reminders = await db.get_pending_prediction_reminders(hours)
            for reminder in reminders:
                text = (
                    "⏰ До начала матча меньше 2 часов\n\n"
                    f"Тур {reminder['round_number']}, матч №{reminder['match_number']}\n"
                    f"{format_match_teams(reminder['home_team'], reminder['away_team'], reminder['home_display_name'], reminder['away_display_name'], reminder['home_country_code'], reminder['away_country_code'], reminder['home_flag_emoji'], reminder['away_flag_emoji'])}\n"
                    f"Начало: {format_kickoff_compact(reminder['kickoff_at'])}\n\n"
                    "Ты ещё не сделал прогноз. Открой бота, чтобы успеть."
                )
                try:
                    await bot.send_message(reminder["telegram_id"], text)
                except Exception:
                    logger.exception(
                        "Не удалось отправить напоминание пользователю %s",
                        reminder["telegram_id"],
                    )
                    continue
                await db.mark_prediction_reminder_sent(
                    reminder["user_id"],
                    reminder["match_id"],
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Не удалось обработать напоминания о прогнозах")
        await asyncio.sleep(interval_seconds)
