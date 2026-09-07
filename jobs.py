import asyncio
import logging

from database import db


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
