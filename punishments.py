import asyncio
import logging

from settings import restricted_users, bot_messages, user_messages, captcha_codes
from settings import (
    CAPCHA_DURATION
)


async def delete_user_messages(context, chat_id, user_id):
    """Удаляет все сообщения пользователя и бота из чата."""
    # Удаляем сообщения пользователя
    if user_id in user_messages:
        for message_id in user_messages[user_id]:
            try:
                await context.bot.delete_message(chat_id=chat_id,
                                                 message_id=message_id)
            except Exception as event:
                logging.error(
                    f"Ошибка при удалении сообщения {message_id} пользователя {user_id}: {event}")
        del user_messages[user_id]  # Удаляем записи о сообщениях пользователя

    # Удаялем сообщения бота
    if user_id in bot_messages:
        for message_id in bot_messages[user_id]:
            try:
                await context.bot.delete_message(chat_id=chat_id,
                                                 message_id=message_id)
            except Exception as event:
                logging.error(
                    f'Ошибка при удалении сообщения {message_id} бота для пользователя {user_id}: {event}')
        del bot_messages[user_id]  # Удаляем записи о сообщениях бота


async def ban_user_after_timeout(context, user_id, chat_id, username):
    """Функция для бана пользователя после истечения времени."""
    await asyncio.sleep(CAPCHA_DURATION)
    if user_id in restricted_users:
        logging.info(
            f"Время ответа истекло для пользователя {username}(id: {user_id})")
        await delete_user_messages(context, chat_id, user_id)
        try:
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            logging.info(
                f"Пользователь {username}(id: {user_id}) забанен за истечение времени")
        except Exception as event:
            logging.error(
                f"Ошибка бана пользователя {username}(id: {user_id}): {event}")
        del restricted_users[user_id]
        del captcha_codes[user_id]