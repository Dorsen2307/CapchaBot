import logging
import asyncio

from telegram import Update
from telegram.ext import ContextTypes
from settings import (
    user_messages,
    restricted_users,
    bot_messages,
    captcha_codes
)
from utils import get_captcha
from settings import (
    COUNT_CHARS_CAPTCHA,
    MAX_ATTEMPTS,
    CAPCHA_DURATION,
    SUPER_USER,
    TIME_DELAY
)
from punishments import delete_user_messages, ban_user_after_timeout


async def check_captcha(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Проверяем, что объект update содержит сообщение и from_user
        if update.message is None or update.message.from_user is None:
            logging.error(
                "Получено обновление без сообщения или информации о пользователе.")
            return  # Завершаем выполнение функции, если данные отсутствуют

        user_id = update.message.from_user.id
        chat_id = update.message.chat.id
        message_text = update.message.text
        username = update.message.from_user.first_name

        # Проверка, что это текстовое сообщение
        if message_text is None:
            logging.warning(
                f"Пользователь {username} (id: {user_id}) отправил не текстовое сообщение.")
            return

        # Если пользователь не находится в состоянии капчи — пропускаем
        if user_id not in restricted_users:
            logging.debug(
                f"Пользователь {username} (id: {user_id}) не находится под капчей. Пропускаем.")
            return

        # Сохраняем идентификатор сообщения, если это первое сообщение пользователя
        if user_id not in user_messages and user_id in restricted_users:
            user_messages[user_id] = []
            # логируем первый ответ пользователя
            logging.info(f'Ответом пользователя {username} (id: {user_id}) было: {message_text}')
        # Сохраняем идентификатор сообщения
        user_messages[user_id].append(update.message.message_id)

        if user_id in restricted_users:
            user_data = restricted_users[user_id]

            # отменяем предыдущую задачу
            if 'ban_task' in user_data and user_data['ban_task']:
                try:
                    user_data['ban_task'].cancel()
                except Exception as e:
                    logging.warning(f"Не удалось отменить задачу таймера для {user_id}: {e}")

            # Проверка длины введенной капчи
            if len(message_text) <= COUNT_CHARS_CAPTCHA:
                if 'attempts' not in user_data:
                    user_data['attempts'] = 0
                user_data['attempts'] += 1

                # проверка капчи
                if 'capcha' in user_data and message_text == user_data['capcha']:
                    logging.info(
                        f"Капча введена верно пользователем {update.message.from_user.username}")

                    # восстанавливаем права пользователя
                    await context.bot.promote_chat_member(chat_id=chat_id,
                                                          user_id=user_id)
                    await context.bot.send_message(
                        chat_id=update.message.chat_id,
                        text=f'Добро пожаловать, [{username}](tg://user?id={user_id})!',
                        parse_mode='Markdown'
                    )

                    await delete_user_messages(context, chat_id,
                                               user_id)  # Удаляем все сообщения пользователя
                    logging.info(
                        f'Сообщения пользователя {update.message.from_user.username} удалены.')

                    # Отменяем задачу таймера
                    if 'ban_task' in user_data and user_data['ban_task']:
                        user_data['ban_task'].cancel()
                    logging.info("Таймер остановлен")

                    del restricted_users[user_id]
                    if user_id in captcha_codes:
                        del captcha_codes[user_id]
                else:
                    if user_data['attempts'] < MAX_ATTEMPTS:
                        logging.info(
                            f"Неправильная капча от пользователя {update.message.from_user.username}. Попытка {user_data['attempts']}.")

                        new_captcha = get_captcha()
                        captcha_codes[user_id] = new_captcha
                        logging.info(f"Создаем новую капчу: {new_captcha}")

                        message = await context.bot.send_message(
                            chat_id=update.message.chat_id,
                            text=f'Попробуйте еще раз! Введите капчу в течении {CAPCHA_DURATION} секунд: {new_captcha}'
                        )  # отправляем сообщение

                        if user_id not in bot_messages:
                            bot_messages[user_id] = []
                        bot_messages[user_id].append(message.message_id)

                        user_data['ban_task'] = asyncio.create_task(
                            ban_user_after_timeout(context, user_id, chat_id,
                                                   update.message.from_user.username))
                        logging.info("Перезапускаем таймер")
                    else:
                        logging.info(
                            f"Пользователь {update.message.from_user.username} превысил максимальное количество попыток.")

                        await delete_user_messages(context, chat_id,
                                                   user_id)  # Удаляем все сообщения пользователя
                        logging.info(
                            f'Сообщения пользователя {update.message.from_user.username} удалены.')

                        await context.bot.ban_chat_member(chat_id=chat_id,
                                                          user_id=user_id)
                        logging.info(
                            f"Пользователь {update.message.from_user.username} забанен за неправильную капчу")

                        if 'ban_task' in user_data and user_data['ban_task']:
                            user_data['ban_task'].cancel()
                        logging.info("Таймер остановлен")

                        await context.bot.send_message(chat_id=chat_id,
                                                       text=f"{SUPER_USER}, обратите внимание на пользователя [{update.message.from_user.username}](tg://user?id={user_id}), он был забанен за неправильные попытки капчи.",
                                                       parse_mode='Markdown'
                                                       )
                        logging.info(
                            f"Отправлено сообщение в чат для {SUPER_USER}")

                        del restricted_users[user_id]
                        if user_id in captcha_codes:
                            del captcha_codes[user_id]
            else:
                logging.info(
                    f"Длина введенной капчи больше допустимой от пользователя {update.message.from_user.username}.")
                message = await context.bot.send_message(
                    chat_id=update.message.chat.id,
                    text=f'Длина введенной капчи превышает допустимую. Пользователь {update.message.from_user.first_name} отправляется в бан.')
                if user_id not in bot_messages:
                    bot_messages[user_id] = []
                bot_messages[user_id].append(message.message_id)

                await asyncio.sleep(
                    TIME_DELAY)  # Задержка перед удалением сообщений
                await delete_user_messages(context, chat_id,
                                           user_id)  # Удаляем все сообщения пользователя
                logging.info(
                    f'Сообщения пользователя {update.message.from_user.username} удалены.')

                await context.bot.ban_chat_member(chat_id=chat_id,
                                                  user_id=user_id)
                logging.info(
                    f"Пользователь {update.message.from_user.username} забанен за неправильную капчу")

                # Отменяем задачу таймера
                if 'ban_task' in user_data and user_data['ban_task']:
                    user_data['ban_task'].cancel()
                logging.info("Таймер остановлен")
    except KeyError as ke:
        logging.error(f"Ошибка KeyError в check_captcha: {ke}")
    except TypeError as te:
        logging.error(f"Ошибка TypeError в check_captcha: {te}")
    except Exception as event:
        logging.error(f"Ошибка при проверке капчи: {event}")
