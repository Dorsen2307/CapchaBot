import asyncio
import logging
import random
import string
import tracemalloc

import nest_asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
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

TOKEN = '8373206965:AAHuaxqk1D6mqiDoeqT31GQWLfISk0SM8Js'

SUPER_USER = '@GameFather40'

TIME_DELAY = 15  # задержка перед удалением пользователя после неверной капчи (чтобы пользователь смог прочитать последнее сообщение)
CAPCHA_DURATION = 60  # Время на ответ капчи (в секундах)
MAX_ATTEMPTS = 3  # Максимальное количество попыток
COUNT_CHARS_CAPTCHA = 6 # Максимальное количество символов для ответа пользователя

restricted_users = {}
captcha_codes = {}
user_messages = {}  # Словарь для хранения идентификаторов сообщений пользователей
bot_messages = {}  # Словарь для хранения идентификаторов сообщений бота


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await get_type_chat(update)

    status = await is_user_banned(context, '1439984311',
                                  update.message.chat.id)
    if status:
        logging.info("Статус: забанен")
    else:
        logging.info("Статус: незабанен")


async def is_user_banned(context, user_id, chat_id):
    try:
        chat_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
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


async def restrict_user(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        new_member = update.message.new_chat_members[0]
        username = new_member.username
        logging.info(f"Новый участник: {username}")

        # Ограничиваем права пользователя
        # await context.bot.restrict_chat_member(
        #     chat_id=update.message.chat.id,
        #     user_id=new_member.id,
        #     permissions=ChatPermissions(
        #         can_send_messages=True,
        #         can_send_polls=False,
        #         can_send_other_messages=False,
        #         can_add_web_page_previews=False,
        #         can_change_info=False,
        #         can_invite_users=False,
        #         can_pin_messages=False
        #     )
        # )
        # logging.info(f"Ограничили права пользователя {new_member.username}")

        # Генерируем капчу
        capcha = ''.join(
            random.choices(string.ascii_letters + string.digits, k=5))
        captcha_codes[new_member.id] = capcha

        # Добавляем в список ограниченных
        restricted_users[new_member.id] = {
            'attempts': 0,
            'capcha': capcha,
            'ban_task': asyncio.create_task(
                ban_user_after_timeout(context, new_member.id,
                                       update.message.chat.id, username))
        }
        message = await context.bot.send_message(
            chat_id=update.message.chat.id,
            # отправляем сообщение пользователю в группу
            text=f'Здравствуйте, {new_member.first_name}! Введите капчу в течении {CAPCHA_DURATION} секунд: {capcha}'
        )
        # Сохраняем идентификатор сообщения бота
        if new_member.id not in bot_messages:
            bot_messages[new_member.id] = []
        bot_messages[new_member.id].append(message.message_id)

    except Exception as event:
        logging.error(
            f"Ошибка при ограничении пользователя {new_member.username}: {event}")


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
            f"Время ответа истекло для пользователя {username}({user_id})")
        await delete_user_messages(context, chat_id, user_id)
        try:
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            # await context.bot.unban_chat_member(chat_id=chat_id,
            #                                     user_id=user_id)  # снимаем бан, чтобы мог вернуться
            logging.info(
                f"Пользователь {username}({user_id}) забанен за истечение времени")
        except Exception as event:
            logging.error(
                f"Ошибка бана пользователя {username}({user_id}): {event}")
        del restricted_users[user_id]
        if user_id in captcha_codes:
            del captcha_codes[user_id]


async def check_capcha(update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.message.from_user.id
        chat_id = update.message.chat.id
        message_text = update.message.text

        # Получаем имя пользователя
        username = update.message.from_user.first_name

        # Сохраняем идентификатор сообщения, если это первое сообщение пользователя
        if user_id not in user_messages:
            user_messages[user_id] = []
        # Сохраняем идентификатор сообщения
        user_messages[user_id].append(update.message.message_id)

        if user_id in restricted_users:
            user_data = restricted_users[user_id]
            user_data['ban_task'].cancel()  # отменяем предыдущую задачу

            # Проверка длины введенной капчи
            if len(message_text) <= COUNT_CHARS_CAPTCHA:
                user_data['attempts'] += 1

                # проверка капчи
                if message_text == user_data['capcha']:
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
                    user_data['ban_task'].cancel()
                    logging.info("Таймер остановлен")

                    del restricted_users[user_id]
                    del captcha_codes[user_id]
                else:
                    if user_data['attempts'] < MAX_ATTEMPTS:
                        logging.info(
                            f"Неправильная капча от пользователя {update.message.from_user.username}. Попытка {user_data['attempts']}.")

                        new_captcha = ''.join(random.choices(
                            string.ascii_letters + string.digits, k=5))
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

                        user_data['ban_task'].cancel()
                        logging.info("Таймер остановлен")

                        await context.bot.send_message(chat_id=chat_id,
                                                       text=f"{SUPER_USER}, обратите внимание на пользователя [{update.message.from_user.username}](tg://user?id={user_id}), он был забанен за неправильные попытки капчи.",
                                                       parse_mode='Markdown'
                                                       )
                        logging.info(
                            f"Отправлено сообщение в чат для {SUPER_USER}")

                        del restricted_users[user_id]
                        del captcha_codes[user_id]

                        # Ограничиваем права пользователя на отправку сообщений
                        # await context.bot.restrict_chat_member(
                        #     chat_id=chat_id,
                        #     user_id=user_id,
                        #     permissions=ChatPermissions(
                        #         can_send_messages=False,
                        #     )
                        # )
                        # logging.info(
                        #     f"Ограничили права на отправку сообщений пользователя {update.message.from_user.username} после неверной капчи")

                        # Сохраняем идентификатор сообщения бота
                        # if user_id not in bot_messages:
                        #     bot_messages[user_id] = []
                        # bot_messages[user_id].append(message.message_id)

                        # await asyncio.sleep(
                        #     TIME_DELAY)  # Задержка перед удалением сообщений

                        # await context.bot.ban_chat_member(chat_id=chat_id,
                        #                                   user_id=user_id)
                        # await context.bot.unban_chat_member(chat_id=chat_id,
                        #                                     user_id=user_id)  # снимаем бан
                        # Отменяем задачу таймера
                        # user_data['ban_task'].cancel()
                        # logging.info(
                        #     f"Пользователь {update.message.from_user.username} забанен за неправильную капчу")
                        # del restricted_users[user_id]
                        # del captcha_codes[user_id]
            else:
                logging.info(
                    f"Длина введенной капчи больше допустимой от пользователя {update.message.from_user.username}.")
                message = await context.bot.send_message(chat_id=update.message.chat.id,
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
                user_data['ban_task'].cancel()
                logging.info("Таймер остановлен")
    except Exception as event:
        logging.error(f"Ошибка при проверке капчи: {event}")


async def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    # application.add_handler(CommandHandler('start', start))
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, restrict_user)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, check_capcha)
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
