from telethon import TelegramClient, events
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
import json
import os
import asyncio
from datetime import datetime
import requests
from requests.exceptions import RequestException
import pytz
import logging
import sys

# Токен вашего бота (чтобы найти: /newbot в @botfather)
BOT_TOKEN = '123123123'

# Ваш ID в Telegram (можно узнать у бота @userinfobot)
YOUR_CHAT_ID = 12345678

# Данные из my.telegram.org/apps
api_id = '123456789'
api_hash = '2A3456Q78S'

# Показывать ли сообщение с помощью в командах? 0 = нет , 1 = да
help_message = 1

session_name = 'session_name'
spy_list_file = 'spy_list.json'
messages_cache_file = 'messages_cache.json'

# Режим разработчика
debug = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("spy_client.log"),  # Логи будут записываться в файл
        # logging.StreamHandler # Логи будут выводиться в консоль
    ]
)
logger = logging.getLogger(__name__)

class SpyClient:
    def __init__(self):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.spy_list = self.load_data(spy_list_file, [])
        self.messages_cache = self.load_data(messages_cache_file, {})
        self.admin_id = None
        self.main_menu_message_id = None  # ID сообщения с главным меню
        self.ignore_messages = {}  # Словарь для игнорирования повторяющихся сообщений

        # Регистрация обработчиков событий
        self.client.on(events.NewMessage)(self.handle_new_message)
        self.client.on(events.MessageEdited)(self.handle_edited_message)
        self.client.on(events.NewMessage)(self.handle_self_destruct_media)

    def load_data(self, filename, default):
        """Загружает данные из JSON-файла или возвращает значение по умолчанию."""
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    data = f.read()
                    return json.loads(data) if data.strip() else default
            except json.JSONDecodeError:
                return default
        return default

    def save_data(self, filename, data):
        """Сохраняет данные в JSON-файл."""
        try:
            temp_filename = filename + ".tmp"
            with open(temp_filename, 'w') as f:
                json.dump(data, f)
            os.replace(temp_filename, filename)
        except Exception as e:
            if debug == 1:
                print(f"Error saving data to {filename}: {e}")

    async def send_message_via_bot(self, text, file=None, max_retries=3, retry_delay=5):
        """
        Отправляет сообщение через Telegram-бота с защитой от сетевых ошибок.

        :param text: Текст сообщения.
        :param file: Путь к файлу (если есть медиа).
        :param max_retries: Максимальное количество попыток отправки (по умолчанию 3).
        :param retry_delay: Задержка между попытками в секундах (по умолчанию 5).
        """
        retries = 0
        while retries < max_retries:
            try:
                if file and os.path.exists(file):  # Если есть медиа, отправляем его с подписью
                    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto' if file.lower().endswith(('.png', '.jpg', '.jpeg')) else f'https://api.telegram.org/bot{BOT_TOKEN}/sendDocument'
                    try:
                        with open(file, 'rb') as f:  # Открываем файл в бинарном режиме
                            files = {'photo' if url.endswith('sendPhoto') else 'document': f}
                            data = {'chat_id': YOUR_CHAT_ID, 'caption': text}  # Подпись к медиа
                            response = requests.post(url, files=files, data=data)
                            if response.status_code != 200:
                                print(f"Ошибка при отправке медиа: {response.text}")
                            else:
                                return  # Успешная отправка
                    except FileNotFoundError:
                        print(f"Файл {file} не найден.")
                        return
                    except Exception as e:
                        print(f"Ошибка при отправке медиа: {e}")
                        retries += 1
                        if retries < max_retries:
                            print(f"Повторная попытка через {retry_delay} секунд...")
                            time.sleep(retry_delay)
                        continue
                else:  # Если медиа нет, отправляем просто текст
                    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
                    data = {
                        'chat_id': YOUR_CHAT_ID,
                        'text': text
                    }
                    try:
                        response = requests.post(url, data=data)
                        if response.status_code != 200:
                            print(f"Ошибка при отправке сообщения: {response.text}")
                        else:
                            return  # Успешная отправка
                    except Exception as e:
                        print(f"Ошибка при отправке сообщения: {e}")
                        retries += 1
                        if retries < max_retries:
                            print(f"Повторная попытка через {retry_delay} секунд...")
                            time.sleep(retry_delay)
                        continue
            except RequestException as e:
                print(f"Сетевая ошибка: {e}")
                retries += 1
                if retries < max_retries:
                    print(f"Повторная попытка через {retry_delay} секунд...")
                    time.sleep(retry_delay)
                continue

        print(f"Не удалось отправить сообщение после {max_retries} попыток.")

    async def handle_new_message(self, event):
        """Обрабатывает новые сообщения."""
        if event.message.message.startswith(('.spy', '.unspy', '.list', '.scan', '.reload')):
            await self.process_command(event)
        else:
            await self.cache_message(event)

    async def process_command(self, event):
        """Обрабатывает команды."""
        sender = await event.get_sender()
        if sender.id != self.admin_id:
            return

        command = event.message.message.split()
        if not command:
            return

        cmd = command[0]
        args = command[1:]

        if cmd == '.list':
            await event.delete()
            await self.show_spy_list(event)
            return

        if cmd == '.scan':
            await event.delete()
            await self.scan_chat(event)
            return

        if cmd == '.reload':
            await event.delete()
            await self.reload_script(event)
            return

        if cmd == '.spy':
            await event.delete()
            if event.is_reply:
                replied_message = await event.get_reply_message()
                target_user = await replied_message.get_sender()
                await self.add_to_spy_list(target_user, event.chat_id, event)
            elif args:
                username_or_id = args[0]
                try:
                    if username_or_id.startswith('@'):
                        target_user = await self.client.get_entity(username_or_id)
                    else:
                        target_user = await self.client.get_entity(int(username_or_id))

                    # Получаем chat_id из диалога с пользователем
                    dialog = await self.client.get_dialogs()
                    for d in dialog:
                        if d.entity.id == target_user.id:
                            chat_id = d.entity.id
                            break
                    else:
                        await self.send_message_via_bot(f"❌ Ошибка: не удалось найти чат с пользователем {username_or_id}.")
                        return

                    # Передаём chat_id из чата пользователя
                    await self.add_to_spy_list(target_user, chat_id, event)
                except Exception as e:
                    await self.send_message_via_bot(f"❌ Ошибка: не удалось найти пользователя {username_or_id}.")
            else:
                await self.send_message_via_bot("❌ Ошибка: укажите пользователя (например, .spy @username или .spy 123456789).")
            return

        if cmd == '.unspy':
            await event.delete()
            if event.is_reply:
                replied_message = await event.get_reply_message()
                target_user = await replied_message.get_sender()
                await self.remove_from_spy_list(target_user, event.chat_id, event)
            elif args:
                username_or_id = args[0]
                try:
                    if username_or_id.startswith('@'):
                        target_user = await self.client.get_entity(username_or_id)
                    else:
                        target_user = await self.client.get_entity(int(username_or_id))
                    await self.remove_from_spy_list(target_user, event.chat_id, event)
                except Exception as e:
                    await self.send_message_via_bot(f"❌ Ошибка: не удалось найти пользователя {username_or_id}.")
            else:
                await self.send_message_via_bot("❌ Ошибка: укажите пользователя (например, .unspy @username или .unspy 123456789).")
            return

    async def reload_script(self, event):
        """Перезагружает скрипт."""
        await self.send_message_via_bot("🔄 Перезагрузка скрипта...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_message_via_bot("❌ TeleSpy отключён."))
        sys.exit(0)

    async def run(self):
        """Запускает клиент и обработчики событий."""
        await self.client.start()
        await self.initialize()
        print("Скрипт запущен!")

        # Запускаем задачу проверки удалённых сообщений
        asyncio.create_task(self.check_deleted_messages())

        # Запускаем основной цикл
        await self.client.run_until_disconnected()

    async def show_spy_list(self, event):
        """Показывает список отслеживаемых пользователей."""
        if not self.spy_list:
            await self.send_message_via_bot("Список отслеживаемых пользователей пуст.")
            return

        spy_list_message = "🕵️ Список отслеживаемых пользователей:\n\n"
        for user_id, chat_id in self.spy_list:
            try:
                user = await self.client.get_entity(user_id)
                username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
                spy_list_message += f"👤 ID: {user_id}, @{username}\n"
            except Exception as e:
                if debug == 1:
                    print(f"Ошибка при получении информации о пользователе {user_id}: {e}")
                spy_list_message += f"👤 ID: {user_id}\n"

        await self.send_message_via_bot(spy_list_message)

    async def add_to_spy_list(self, target_user, chat_id, event):
        """Добавляет пользователя в список отслеживания."""
        entry = [target_user.id, chat_id]

        # Проверяем, не добавлен ли пользователь уже
        if entry in self.spy_list:
            username = target_user.username or f"{target_user.first_name or ''} {target_user.last_name or ''}".strip()
            display_name = f"@{username}" if target_user.username else username
            logger.info(f"Пользователь {display_name} уже добавлен в список отслеживания.")
            await self.send_message_via_bot(f'ℹ️ Пользователь {display_name} уже добавлен в список отслеживания!')
            return

        # Добавляем пользователя в список
        self.spy_list.append(entry)
        self.save_data(spy_list_file, self.spy_list)
        username = target_user.username or f"{target_user.first_name or ''} {target_user.last_name or ''}".strip()
        display_name = f"@{username}" if target_user.username else username
        logger.info(f"Пользователь {display_name} добавлен в список отслеживания. Chat ID: {chat_id}")
        await self.send_message_via_bot(f'🕵️ Пользователь {display_name} добавлен в список отслеживания!')

    async def remove_from_spy_list(self, target_user, chat_id, event):
        """Удаляет пользователя из списка отслеживания."""
        user_id = target_user.id

        # Удаляем все записи, связанные с этим пользователем
        initial_length = len(self.spy_list)
        self.spy_list = [entry for entry in self.spy_list if entry[0] != user_id]

        if len(self.spy_list) < initial_length:
            self.save_data(spy_list_file, self.spy_list)
            username = target_user.username or f"{target_user.first_name or ''} {target_user.last_name or ''}".strip()
            display_name = f"@{username}" if target_user.username else username
            await self.send_message_via_bot(f'❌ Пользователь {display_name} удалён из списка отслеживания!')
        else:
            await self.send_message_via_bot(f'ℹ️ Пользователь не найден в списке отслеживания.')

    async def cache_message(self, event):
        """Кэширует сообщения отслеживаемых пользователей."""
        sender = await event.get_sender()
        chat_id = event.chat_id

        # Проверяем, добавлен ли пользователь в список отслеживания
        if [sender.id, chat_id] in self.spy_list:
            message_id = str(event.message.id)
            chat_id_str = str(chat_id)

            if chat_id_str not in self.messages_cache:
                self.messages_cache[chat_id_str] = {}

            # Проверяем, не существует ли уже сообщение с таким же ID в кэше
            if message_id in self.messages_cache[chat_id_str]:
                logger.info(f"Сообщение {message_id} уже закэшировано. Пропускаем.")
                return  # Пропускаем дубликаты

            # Сохраняем медиа на диск (если есть)
            media_path = None
            if event.message.media:
                try:
                    media_path = await event.message.download_media(file=f"temp_media/{chat_id_str}_{message_id}")
                    logger.info(f"Медиа сохранено: {media_path}")
                except Exception as e:
                    logger.error(f"Ошибка при сохранении медиа: {e}")

            # Преобразуем дату отправки в локальный часовой пояс
            utc_date = event.message.date  # Дата в UTC
            local_tz = pytz.timezone('Europe/Moscow')  # Укажите ваш часовой пояс
            local_date = utc_date.replace(tzinfo=pytz.utc).astimezone(local_tz)

            # Сохраняем сообщение в кэш с датой отправки
            self.messages_cache[chat_id_str][message_id] = {
                'user_id': sender.id,
                'text': event.message.text,
                'media_path': media_path,  # Путь к сохранённому медиа
                'date_sent': local_date.isoformat(),  # Дата отправки в локальном времени
                'date_deleted': None  # Дата удаления (пока неизвестна)
            }
            self.save_data(messages_cache_file, self.messages_cache)
            logger.info(f"Сообщение {message_id} закэшировано. Chat ID: {chat_id}")

    async def handle_edited_message(self, event):
        """Обрабатывает редактированные сообщения."""
        chat_id_str = str(event.chat_id)
        message_id = str(event.message.id)

        if chat_id_str in self.messages_cache and message_id in self.messages_cache[chat_id_str]:
            cached = self.messages_cache[chat_id_str][message_id]
            user = await self.client.get_entity(cached['user_id'])

            # Формируем имя пользователя с "@", если юзернейм есть
            username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
            display_name = f"@{username}" if user.username else username

            if event.message.text != cached['text']:  # Проверяем изменения в тексте
                message = f"✏️ {display_name} изменил сообщение!\n\n"
                message += f"Было: 📝 {cached['text']}\n💬 {event.message.text}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                # Если есть медиа, отправляем его с подписью
                if cached['media_path'] and os.path.exists(cached['media_path']):
                    await self.send_message_via_bot(message, file=cached['media_path'])
                else:
                    await self.send_message_via_bot(message)

            # Обновляем кэш
            self.messages_cache[chat_id_str][message_id]['text'] = event.message.text
            self.save_data(messages_cache_file, self.messages_cache)

    async def handle_self_destruct_media(self, event):
        """Обрабатывает самоуничтожающиеся медиа."""
        if event.message.media and hasattr(event.message.media, 'ttl_seconds'):
            ttl_seconds = event.message.media.ttl_seconds
            if ttl_seconds is not None and ttl_seconds > 0:  # Проверяем, что ttl_seconds не None и больше 0
                try:
                    media_path = await event.message.download_media(file="temp_media/")
                    sender = await event.get_sender()
                    username = sender.username or f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                    display_name = f"@{username}" if sender.username else username
                    info_message = f"📸 {display_name} отправил одноразовое сообщение!\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    await self.send_message_via_bot(info_message, file=media_path)
                    os.remove(media_path)
                except Exception as e:
                    if debug == 1:
                        print(f"Ошибка при обработке одноразового медиа: {e}")

    async def check_deleted_messages(self):
        """Проверяет удаленные сообщения в кэше."""
        while True:
            try:
                logger.info("Начинаем проверку удалённых сообщений...")
                for chat_id_str, messages in list(self.messages_cache.items()):
                    chat_id = int(chat_id_str)
                    deleted_messages = []
                    logger.info(f"Проверяем чат {chat_id} на удалённые сообщения.")

                    for message_id_str, cached_message in list(messages.items()):
                        message_id = int(message_id_str)
                        try:
                            logger.info(f"Проверяем сообщение {message_id} в чате {chat_id}.")
                            # Проверяем, существует ли сообщение в чате
                            message = await self.client.get_messages(chat_id, ids=message_id)
                            if message is None:  # Сообщение удалено
                                logger.info(f"Сообщение {message_id} в чате {chat_id} удалено.")
                                # Проверяем, есть ли дата отправки в кэше
                                if 'date_sent' not in cached_message:
                                    # Увеличиваем счётчик для этого сообщения
                                    self.ignore_messages[message_id_str] = self.ignore_messages.get(message_id_str, 0) + 1
                                    if self.ignore_messages[message_id_str] <= 5:
                                        logger.info(f"Сообщение {message_id} в чате {chat_id} не содержит даты отправки. Пропускаем.")
                                    continue

                                # Если сообщение было пропущено более 5 раз, игнорируем его
                                if self.ignore_messages.get(message_id_str, 0) > 5:
                                    logger.info(f"Сообщение {message_id} в чате {chat_id} пропущено более 5 раз. Игнорируем.")
                                    continue

                                # Преобразуем дату удаления в локальный часовой пояс
                                utc_now = datetime.now(pytz.utc)  # Текущее время в UTC
                                local_tz = pytz.timezone('Europe/Moscow')  # Укажите ваш часовой пояс
                                local_now = utc_now.astimezone(local_tz)

                                # Добавляем дату удаления
                                cached_message['date_deleted'] = local_now.isoformat()
                                deleted_messages.append((message_id_str, cached_message))
                                logger.info(f"Сообщение {message_id} в чате {chat_id} добавлено в список удалённых.")
                        except Exception as e:
                            logger.error(f"Ошибка при проверке сообщения {message_id} в чате {chat_id}: {e}")
                            continue

                    # Сортируем удалённые сообщения по дате отправки (от старых к новым)
                    deleted_messages.sort(key=lambda x: datetime.fromisoformat(x[1]['date_sent']))

                    # Обрабатываем удаленные сообщения
                    for message_id_str, cached_message in deleted_messages:
                        try:
                            user = await self.client.get_entity(cached_message['user_id'])
                            username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
                            display_name = f"@{username}" if user.username else username

                            # Формируем сообщение с датой отправки и датой удаления
                            date_sent = datetime.fromisoformat(cached_message['date_sent']).strftime('%Y-%m-%d %H:%M:%S')
                            date_deleted = datetime.fromisoformat(cached_message['date_deleted']).strftime('%Y-%m-%d %H:%M:%S')
                            info_message = (
                                f"🗑 {display_name} удалил сообщение!\n"
                                f"📅 Дата отправки: {date_sent}\n"
                                f"🗓️ Дата удаления: {date_deleted}\n\n"
                            )
                            if cached_message['text']:
                                info_message += f"💬 {cached_message['text']}\n\n"

                            # Если есть медиа, отправляем его с подписью
                            if cached_message['media_path'] and os.path.exists(cached_message['media_path']):
                                logger.info(f"Отправляем медиа с сообщением: {info_message}")
                                await self.send_message_via_bot(info_message, file=cached_message['media_path'])
                            else:
                                logger.info(f"Отправляем текстовое сообщение: {info_message}")
                                await self.send_message_via_bot(info_message)

                            # Удаляем сообщение из кэша
                            del self.messages_cache[chat_id_str][message_id_str]
                            logger.info(f"Сообщение {message_id} удалено из кэша.")
                        except Exception as e:
                            logger.error(f"Ошибка при обработке удалённого сообщения {message_id}: {e}")

                    # Сохраняем обновленный кэш
                    if not self.messages_cache[chat_id_str]:  # Если чат пуст, удаляем его из кэша
                        del self.messages_cache[chat_id_str]
                    self.save_data(messages_cache_file, self.messages_cache)

                await asyncio.sleep(5)  # Проверяем каждые 5 секунд
            except Exception as e:
                logger.error(f"Ошибка в check_deleted_messages: {e}")
                await asyncio.sleep(10)  # Если ошибка, ждем 10 секунд перед повторной попыткой

    async def scan_chat(self, event):
        """Сканирует весь чат и кэширует все сообщения с учётом даты отправки."""
        chat_id = event.chat_id
        chat_id_str = str(chat_id)
        await self.send_message_via_bot(f"✅ Чат {chat_id} сканируется.")

        if chat_id_str not in self.messages_cache:
            self.messages_cache[chat_id_str] = {}

        # Получаем все сообщения из чата
        messages = []
        async for message in self.client.iter_messages(chat_id):  # Лимит можно изменить
            messages.append(message)

        # Сортируем сообщения по дате отправки (от старых к новым)
        messages.sort(key=lambda msg: msg.date)

        # Кэшируем сообщения
        for message in messages:
            message_id = str(message.id)
            if message_id in self.messages_cache[chat_id_str]:
                continue  # Пропускаем дубликаты

            sender = await message.get_sender()
            if [sender.id, chat_id] in self.spy_list:
                media_path = None
                if message.media:
                    try:
                        media_path = await message.download_media(file=f"temp_media/{chat_id_str}_{message_id}")
                    except Exception as e:
                        if debug != 0:
                            print(f"Ошибка при сохранении медиа: {e}")

                # Преобразуем дату отправки в локальный часовой пояс
                utc_date = message.date  # Дата в UTC
                local_tz = pytz.timezone('Europe/Moscow')  # Укажите ваш часовой пояс
                local_date = utc_date.replace(tzinfo=pytz.utc).astimezone(local_tz)

                # Сохраняем сообщение в кэш с датой отправки
                self.messages_cache[chat_id_str][message_id] = {
                    'user_id': sender.id,
                    'text': message.text,
                    'media_path': media_path,
                    'date_sent': local_date.isoformat(),  # Дата отправки в локальном времени
                    'date_deleted': None  # Дата удаления (пока неизвестна)
                }
        self.save_data(messages_cache_file, self.messages_cache)
        await self.send_message_via_bot(f"✅ Чат {chat_id} просканирован!")


    async def initialize(self):
        """Инициализация: получаем ID текущего пользователя."""
        me = await self.client.get_me()
        self.admin_id = me.id
        # Отправляем уведомление о успешном запуске
        await self.send_message_via_bot("✅ TeleSpy подключён и работает!")
        if help_message != 0:
            await self.send_message_via_bot("Как пользоваться ботом ❓\n\n.spy [ответ на сообщение/@юзернейм или ID] - включить слежку🕵️✅\n.unspy [ответ на сообщение/@юзернейм или ID] - выключить слежку 🕵️❌\n.spy_list - вывод списка прослеживаемых 🕵️📝\n.scan - отсканировать чат для прослушки 📜✍️\n.reload - перезагрузить бота 🤖")

async def main():
    spy_client = SpyClient()
    await spy_client.run()

if __name__ == '__main__':
    spy_client = SpyClient()
    spy_client.client.loop.run_until_complete(main())
