import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from handlers.admin import router as admin_router
from handlers.user import router as user_router
from jobs import lock_started_matches_loop


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def main():
    await db.create_tables()

    bot = Bot(token=BOT_TOKEN)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)

    locker = asyncio.create_task(lock_started_matches_loop())
    print("Бот запущен...")
    try:
        await dispatcher.start_polling(bot)
    finally:
        locker.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
