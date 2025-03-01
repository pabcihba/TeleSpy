from telethon import TelegramClient, events
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
from telethon.tl.functions.users import GetFullUserRequest
import json
import os
import asyncio
from datetime import datetime

#меняй на свои значения
api_id = '1234'
api_hash = '1234'

#меняй не меняй толку нет
debug = 0

#ниже не стоит менять
session_name = 'session_name'
spy_list_file = 'spy_list.json'
messages_cache_file = 'messages_cache.json'

#о великий и могучий deepseek

class SpyClient:
    def __init__(self):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.spy_list = self.load_data(spy_list_file, [])
        self.messages_cache = self.load_data(messages_cache_file, {})
        self.admin_id = None  # Инициализируем admin_id как None
        self.profile_cache = {}  # Кэш для хранения данных профиля

        # Регистрируем обработчики событий
        self.client.on(events.NewMessage)(self.handle_new_message)
        self.client.on(events.MessageEdited)(self.handle_edited_message)
        self.client.on(events.NewMessage)(self.handle_self_destruct_media)

        # Запускаем периодическую проверку удалённых сообщений и профилей
        self.client.loop.create_task(self.check_deleted_messages())
        self.client.loop.create_task(self.check_profile_changes())


    async def initialize(self):
        """Инициализация: получаем ID текущего пользователя."""
        me = await self.client.get_me()
        self.admin_id = me.id  # Сохраняем ваш ID

    def load_data(self, filename, default):
        """Загружает данные из JSON-файла или возвращает значение по умолчанию."""
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    data = f.read()
                    if data.strip():  # Проверяем, что файл не пустой
                        return json.loads(data)
                    else:
                        return default
            except json.JSONDecodeError:
                # Если файл повреждён, возвращаем значение по умолчанию
                return default
        return default

    def save_data(self, filename, data):
        """Сохраняет данные в JSON-файл."""
        try:
            # Создаём временный файл для записи
            temp_filename = filename + ".tmp"
            with open(temp_filename, 'w') as f:
                json.dump(data, f)

            # Переименовываем временный файл в основной
            os.replace(temp_filename, filename)
        except Exception as e:
            if debug == 1:
                print(f"Error saving data to {filename}: {e}")

    async def handle_new_message(self, event):
        # Обработка команд
        if event.message.message.startswith(('.spy', '.unspy', '.spy_list')):
            await self.process_command(event)
        else:
            await self.cache_message(event)

    async def process_command(self, event):
        try:
            # Кто отправил команду
            sender = await event.get_sender()
            chat_id = event.chat_id
            command = event.message.message

            # Проверяем, что команду отправил администратор (вы)
            if sender.id != self.admin_id:
                return  # Игнорируем команду, если отправитель не вы

            # На кого нацелена команда
            if command == '.spy_list':
                await self.show_spy_list(event)
                await event.delete()  # Удаляем команду из чата
                return

            if event.is_reply:  # Если команда отправлена в ответ на сообщение
                replied_message = await event.get_reply_message()
                target_user = await replied_message.get_sender()
            else:  # Если команда отправлена без ответа
                await event.reply("❌ Ошибка: команда должна быть отправлена в ответ на сообщение пользователя.")
                return

            if command == '.spy':
                await self.add_to_spy_list(target_user, chat_id, event)
            elif command == '.unspy':
                await self.remove_from_spy_list(target_user, chat_id, event)

            await event.delete()

        except Exception as e:
            if debug == 1:
                print(f"Error processing command: {e}")


    async def show_spy_list(self, event):
        """Выводит список пользователей, на которых включена слежка."""
        try:
            if not self.spy_list:
                await self.client.send_message('me', "Список отслеживаемых пользователей пуст.")
                return

            spy_list_message = "🕵️ Список отслеживаемых пользователей:\n\n"
            for entry in self.spy_list:
                user_id, chat_id = entry
                try:
                    user = await self.client.get_entity(user_id)
                    username = user.username
                    if username:
                        spy_list_message += f"👤 ID: {user_id},@{username}\n"
                    else:
                        # Если юзернейма нет, используем имя и фамилию
                        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                        spy_list_message += f"👤 ID: {user_id}, Имя: {full_name}\n"
                except Exception as e:
                    if debug == 1:
                        print(f"Ошибка при получении информации о пользователе {user_id}: {e}")
                    spy_list_message += f"👤 ID: {user_id}\n"

            await self.client.send_message('me', spy_list_message)
        except Exception as e:
            if debug == 1:
                print(f"Ошибка при формировании списка отслеживаемых пользователей: {e}")
            await self.client.send_message('me', "❌ Ошибка при формировании списка отслеживаемых пользователей.")

    async def add_to_spy_list(self, target_user, chat_id, event):
        entry = [target_user.id, chat_id]
        if entry not in self.spy_list:
            self.spy_list.append(entry)
            self.save_data(spy_list_file, self.spy_list)
            username = target_user.username or target_user.first_name
            await self.client.send_message(
                'me',
                f'🕵️ Пользователь @{username} добавлен в список отслеживания!'
            )

            # Получаем полную информацию о пользователе через API
            full_user = await self.client(GetFullUserRequest(target_user))
            self.profile_cache[target_user.id] = {
                'first_name': target_user.first_name,
                'last_name': target_user.last_name,
                'username': target_user.username,
                'photo_id': target_user.photo.photo_id if target_user.photo else None,
                'about': full_user.about if hasattr(full_user, 'about') else None  # Описание профиля
            }
            self.save_data(messages_cache_file, self.messages_cache)

    async def check_profile_changes(self):
        """Периодически проверяет изменения аватарок и ников отслеживаемых пользователей."""
        while True:
            try:
                # Проверяем, что клиент подключён
                if not self.client.is_connected():
                    await self.client.connect()

                for entry in self.spy_list:
                    user_id, chat_id = entry
                    try:
                        # Получаем информацию о пользователе через API
                        full_user = await self.client(GetFullUserRequest(user_id))
                        user = full_user.users[0]  # Получаем объект пользователя
                        cached_profile = self.profile_cache.get(user_id, {})

                        # Проверяем изменения в профиле
                        changes = []
                        if user.first_name != cached_profile.get('first_name'):
                            changes.append(f"📝 Имя: {cached_profile.get('first_name')} → {user.first_name}")
                        if user.last_name != cached_profile.get('last_name'):
                            changes.append(f"📝 Фамилия: {cached_profile.get('last_name')} → {user.last_name}")
                        if user.username != cached_profile.get('username'):
                            changes.append(f"📝 Юзернейм: @{cached_profile.get('username')} → @{user.username}")

                        # Проверяем аватарку
                        if user.photo and user.photo.photo_id != cached_profile.get('photo_id'):
                            changes.append("📸 Аватарка изменена")
                            # Скачиваем новую аватарку
                            photo_path = await self.client.download_profile_photo(user)
                            if photo_path:
                                changes.append("(Новая аватарка прикреплена)")

                        # Если есть изменения, отправляем уведомление
                        if changes:
                            message = f"🔄 @{user.username or user.first_name} изменил профиль:\n\n"
                            message += "\n".join(changes)
                            if user.photo and user.photo.photo_id != cached_profile.get('photo_id'):
                                # Отправляем текстовое сообщение и новую аватарку
                                await self.client.send_message('me', message, file=photo_path)
                            else:
                                # Отправляем только текстовое сообщение
                                await self.client.send_message('me', message)

                            # Обновляем кэш профиля
                            self.profile_cache[user_id] = {
                                'first_name': user.first_name,
                                'last_name': user.last_name,
                                'username': user.username,
                                'photo_id': user.photo.photo_id if user.photo else None
                            }
                            self.save_data(messages_cache_file, self.messages_cache)

                    except Exception as e:
                        if debug == 1:
                            print(f"Ошибка при проверке профиля пользователя {user_id}: {e}")

                await asyncio.sleep(10)  # Проверяем каждые 10 секунд
            except Exception as e:
                if debug == 1:
                    print(f"Ошибка в check_profile_changes: {e}")
                await asyncio.sleep(10)  # Если ошибка, ждём 10 секунд перед повторной попыткой

    async def remove_from_spy_list(self, target_user, chat_id, event):
            entry = [target_user.id, chat_id]
            if entry in self.spy_list:
                self.spy_list.remove(entry)
                self.save_data(spy_list_file, self.spy_list)
                username = target_user.username or target_user.first_name
                await self.client.send_message(
                    'me',
                    f'❌ Пользователь @{username} удалён из списка отслеживания!'
                )

    async def cache_message(self, event):
        try:
            sender = await event.get_sender()
            chat_id = event.chat_id
            if [sender.id, chat_id] in self.spy_list:
                message_id = str(event.message.id)
                chat_id_str = str(chat_id)

                if chat_id_str not in self.messages_cache:
                    self.messages_cache[chat_id_str] = {}


                self.messages_cache[chat_id_str][message_id] = {
                    'user_id': sender.id,
                    'text': event.message.text,
                    'media': event.message.media,
                    'date': event.message.date.isoformat()  #тут дата
                }
                self.save_data(messages_cache_file, self.messages_cache)

        except Exception as e:
            if debug == 1:
                print(f"Error caching message: {e}")

    async def handle_edited_message(self, event):
        try:
            chat_id = event.chat_id
            message_id = str(event.message.id)
            chat_id_str = str(chat_id)

            if chat_id_str in self.messages_cache and message_id in self.messages_cache[chat_id_str]:
                cached = self.messages_cache[chat_id_str][message_id]
                user = await self.client.get_entity(cached['user_id'])

                if event.message.text != cached['text'] or event.message.media != cached['media']:

                    message = f"✏️ @{user.username} изменил сообщение!\n\n"

                    if event.message.text != cached['text']:
                        message += f"Было: 📝 {cached['text']}\n"
                        message += f"💬 {event.message.text}\n\n"
                        message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                    if event.message.media:
                        await self.client.send_message('me', message, file=event.message.media)
                    else:
                        await self.client.send_message('me', message)

                    #делаем кэш
                    self.messages_cache[chat_id_str][message_id]['text'] = event.message.text
                    self.messages_cache[chat_id_str][message_id]['media'] = event.message.media
                    self.save_data(messages_cache_file, self.messages_cache)

        except Exception as e:
            if debug == 1:
                print(f"Error handling edit: {e}")

    async def check_deleted_messages(self):
        while True:
            try:
                for chat_id_str, messages in self.messages_cache.items():
                    chat_id = int(chat_id_str)
                    deleted_messages = []  # Список для хранения удалённых сообщений

                    # Получаем все сообщения из кэша для текущего чата
                    for message_id_str, cached_message in list(messages.items()):
                        message_id = int(message_id_str)

                        # Проверяем, существует ли сообщение в чате
                        try:
                            message = await self.client.get_messages(chat_id, ids=message_id)
                            if not message:
                                # Сообщение удалено, добавляем в список
                                deleted_messages.append((message_id_str, cached_message))
                        except Exception as e:
                            if debug == 1:
                                print(f"Error checking message {message_id} in chat {chat_id}: {e}")

                    # Сортируем удалённые сообщения по дате отправки
                    deleted_messages.sort(key=lambda x: x[1]['date'])

                    # Обрабатываем все удалённые сообщения в порядке их отправки
                    for message_id_str, cached_message in deleted_messages:
                        user = await self.client.get_entity(cached_message['user_id'])
                        if [cached_message['user_id'], chat_id] in self.spy_list:
                            # Формируем текстовое сообщение с информацией об удалении
                            info_message = f"🗑 @{user.username} удалил сообщение!\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

                            # Если это стикер, отправляем текстовое сообщение и стикер
                            if cached_message['media'] and hasattr(cached_message['media'], 'document'):
                                # Отправляем текстовое сообщение
                                await self.client.send_message('me', info_message)
                                # Отправляем стикер
                                await self.client.send_file('me', cached_message['media'])
                            else:
                                # Если это не стикер, отправляем текстовое сообщение с текстом или медиа
                                if cached_message['text']:
                                    info_message += f"💬 {cached_message['text']}"
                                await self.client.send_message('me', info_message, file=cached_message['media'])

                        # Удаляем из кэша
                        del self.messages_cache[chat_id_str][message_id_str]
                        self.save_data(messages_cache_file, self.messages_cache)

                await asyncio.sleep(1)  # Проверяем каждую секунду
            except Exception as e:
                if debug == 1:
                    print(f"Error in check_deleted_messages: {e}")
                await asyncio.sleep(5)  # Если ошибка, ждём 5 секунд перед повторной попыткой

    async def handle_self_destruct_media(self, event):
        """Обрабатывает одноразовые медиафайлы."""
        try:
            # Проверяем, является ли медиафайл одноразовым
            if (
                event.message.media
                and hasattr(event.message.media, 'ttl_seconds')
                and event.message.media.ttl_seconds > 0  # Убедимся, что это действительно одноразовое медиа
            ):
                # Скачиваем медиафайл
                media_path = await event.message.download_media(file="temp_media/")

                # Отправляем текстовое сообщение с информацией об удалении
                sender = await event.get_sender()
                username = sender.username or f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                info_message = f"📸 @{username} отправил одноразовое сообщение!\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                # Отправляем текстовое сообщение и медиафайл
                await self.client.send_message('me', info_message, file=media_path)

                # Удаляем временный файл
                os.remove(media_path)
        except Exception as e:
            if debug == 1:
                print(f"Ошибка при обработке одноразового медиа: {e}")

    async def run(self):
        await self.client.start()

        self.client.on(events.NewMessage)(self.handle_self_destruct_media)

        await self.client.run_until_disconnected()

async def main():
    spy_client = SpyClient()
    await spy_client.client.start()
    await spy_client.initialize()  # Инициализируем admin_id
    print("Скрипт запущен!")
    await spy_client.client.run_until_disconnected()

if __name__ == '__main__':
    spy_client = SpyClient()
    spy_client.client.loop.run_until_complete(main())

