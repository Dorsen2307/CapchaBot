import logging
import random
import string

def get_captcha() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=5))


async def is_user_banned(context, user_id, chat_id):
    """Проверяет пользователя на БАН"""
    try:
        chat_member = await context.bot.get_chat_member(chat_id=chat_id,
                                                        user_id=user_id)
        if chat_member.status == 'kicked':
            return True  # Пользователь забанен
        else:
            return False  # Пользователь не забанен
    except Exception as event:
        logging.error(f"Ошибка при получении статуса пользователя: {event}")
        return False  # Если произошла ошибка, предполагаем, что пользователь не забанен


async def get_type_chat(update) -> None:
    """Определяет тип чата"""
    chat = update.message.chat  # Получаем объект Chat

    if chat.type == "private":
        logging.info("Это личный чат")
    elif chat.type == "group":
        logging.info("Это обычная группа")
    elif chat.type == "supergroup":
        logging.info("Это супергруппа")
    elif chat.type == "channel":
        logging.info("Это канал")
    else:
        logging.info("Неизвестный тип чата")