import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from db import init_db, upsert_user
from handlers import client, admin

logging.basicConfig(level=logging.INFO)

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(client.router)

    # помечаем админов из .env
    for admin_id in ADMIN_IDS:
        upsert_user(admin_id, None, "admin")
        # отметим is_admin=1
        from db import get_db
        with get_db() as db:
            db.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (admin_id,))

    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())