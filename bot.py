import asyncio
import logging
import tracemalloc

import nest_asyncio
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters
)

from check import check_captcha
from restrict import restrict_user
from settings import (
    TOKEN
)

nest_asyncio.apply()
tracemalloc.start()

# Настройка логирования для консоли
# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )

# Настройка логирования в файл
logging.basicConfig(
    filename='bot.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)
# Установим уровень логирования для httpx на WARNING, чтобы INFO-сообщения не показывались
logging.getLogger("httpx").setLevel(logging.WARNING)


async def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    # application.add_handler(CommandHandler('start', start))
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, restrict_user)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, check_captcha)
    )
    logging.info("Бот запущен...")

    try:
        await application.run_polling()
    except asyncio.CancelledError:
        logging.info("Бот завершает работу...")
    except Exception as event:
        logging.error(f'Произошла ошибка: {event}')


if __name__ == '__main__':
    try:
        asyncio.run(main())  # Запускает основную функцию
    except RuntimeError as e:
        if 'asyncio.run() cannot be called from a running event loop' in str(
                e):
            asyncio.get_event_loop().create_task(main())
            asyncio.get_event_loop().run_forever()
        else:
            raise
