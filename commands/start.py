import logging

from telegram import Update
from telegram.ext import ContextTypes
from utils import is_user_banned, get_type_chat


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выполняет команду /start"""
    await get_type_chat(update)

    status = await is_user_banned(context, '1439984311',
                                  update.message.chat.id)
    if status:
        logging.info("Статус: забанен")
    else:
        logging.info("Статус: незабанен")