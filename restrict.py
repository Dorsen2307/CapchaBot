import logging
import asyncio

from punishments import ban_user_after_timeout
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from settings import (
    CAPCHA_DURATION,
    captcha_codes,
    restricted_users,
    bot_messages,

)
from utils import get_captcha



async def restrict_user(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Проверяем, есть ли новые участники
        if not update.message or not update.message.new_chat_members:
            return

        new_member = update.message.new_chat_members[0]
        user_id = new_member.id
        chat_id = update.message.chat.id
        username = new_member.username or new_member.first_name or "Неизвестный пользователь"

        # Проверяем, не был ли пользователь уже участником чата до этого
        try:
            chat_member = await context.bot.get_chat_member(chat_id=chat_id,
                                                            user_id=user_id)
            if chat_member.status in [ChatMember.MEMBER,
                                      ChatMember.ADMINISTRATOR,
                                      ChatMember.OWNER]:
                logging.info(
                    f"Пользователь {username} (id: {user_id}) уже был в чате. Пропускаем.")
                return
        except Exception as exc:
            # Если пользователь не найден в чате, значит, это действительно новый
            logging.debug(
                f"Пользователь {username} (id: {user_id}) не найден в членстве чата.")

        logging.info(f"Новый участник: {username} (id: {user_id})")

        # Генерируем капчу
        captcha = get_captcha()
        captcha_codes[new_member.id] = captcha

        # Добавляем в список ограниченных
        restricted_users[new_member.id] = {
            'attempts': 0,
            'captcha': captcha,
            'ban_task': asyncio.create_task(
                ban_user_after_timeout(context, user_id, chat_id, username)
            )
        }

        message = await context.bot.send_message(
            chat_id=chat_id,
            # отправляем сообщение пользователю в группу
            text=f'Здравствуйте, {new_member.first_name}! Введите капчу в течении {CAPCHA_DURATION} секунд: {captcha}'
        )
        # Сохраняем идентификатор сообщения бота
        if user_id not in bot_messages:
            bot_messages[user_id] = []
        bot_messages[user_id].append(message.message_id)

    except IndexError:
        logging.warning("Список новых участников пустой.")
    except KeyError as ke:
        logging.error(f"Ошибка KeyError при ограничении пользователя: {ke}")
    except Exception as event:
        logging.error(
            f"Ошибка при ограничении пользователя {username}: {event}")