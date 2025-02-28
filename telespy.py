from telethon import TelegramClient, events
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
import json
import os
import asyncio
from datetime import datetime

#меняй на свои значения
api_id = '12345678'
api_hash = '1234567812345678'

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

        self.client.on(events.NewMessage)(self.handle_new_message)
        self.client.on(events.MessageEdited)(self.handle_edited_message)

        # Запускаем периодическую проверку удалённых сообщений
        self.client.loop.create_task(self.check_deleted_messages())

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
        #ВОТ ТУТ МОЖНО РЫПНУТЬСЯ
        if event.message.message in ('.spy', '.unspy'):
            await self.process_command(event)
        else:
            await self.cache_message(event)

    async def process_command(self, event):
        try:
            #кто отправил команду
            sender = await event.get_sender()
            chat_id = event.chat_id
            command = event.message.message

            #на кого нацелена команда
            if event.is_reply:
                replied_message = await event.get_reply_message()
                target_user = await replied_message.get_sender()
            else:
                await event.reply("❌ Ошибка: команда должна быть отправлена в ответ на сообщение пользователя.")
                return

            if command == '.spy':
                await self.add_to_spy_list(target_user, chat_id, event)
            else:
                await self.remove_from_spy_list(target_user, chat_id, event)

            await event.delete()

        except Exception as e:
            if debug == 1:
                print(f"Error processing command: {e}")

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
                    for message_id_str, cached_message in messages.items():
                        message_id = int(message_id_str)

                        #проверяем, существует ли сообщение в чате
                        try:
                            message = await self.client.get_messages(chat_id, ids=message_id)
                            if not message:
                                #удалил сообщение
                                user = await self.client.get_entity(cached_message['user_id'])
                                if [cached_message['user_id'], chat_id] in self.spy_list:
                                    message = f"🗑 @{user.username} удалил сообщение!\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

                                    if cached_message['text']:
                                        message += f"💬 {cached_message['text']}"

                                    
                                    if cached_message['media']:
                                        await self.client.send_message('me', message, file=cached_message['media'])
                                    else:
                                        await self.client.send_message('me', message)

                                #удаляем из кэша
                                del self.messages_cache[chat_id_str][message_id_str]
                                self.save_data(messages_cache_file, self.messages_cache)
                        except Exception as e:
                            if debug == 1:
                                print(f"Error checking message {message_id} in chat {chat_id}: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                if debug == 1:
                    print(f"Error in check_deleted_messages: {e}")

    async def handle_self_destruct_media(self, event):
        try:
            #хм а если медиафайл исчезающий
            if (
                event.message.media
                and hasattr(event.message.media, 'ttl_seconds')
                and event.message.media.ttl_seconds > 0  # Убедимся, что это действительно исчезающее медиа
            ):
                #скачиваем нюдсы
                media_path = await event.message.download_media(file="temp_media/")

                await self.client.send_message(
                    'me',
                    "📸 Одноразовое сообщение!",
                    file=media_path
                )

                #удаляем порнуху пока не видит мама
                os.remove(media_path)
        except Exception as e:
            if debug == 1:
                print(f"Error handling self-destruct media: {e}")

    async def run(self):
        await self.client.start()

        self.client.on(events.NewMessage)(self.handle_self_destruct_media)

        await self.client.run_until_disconnected()

if __name__ == '__main__':
    spy_client = SpyClient()
    print('TeleSpy started!')
    spy_client.client.loop.run_until_complete(spy_client.run())
