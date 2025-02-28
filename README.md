# TeleSpy 🕵️
Cохраняй саморазрушающиеся файлы и следи за изменениями сообщений
## Принцип работы ❓
![image](https://github.com/user-attachments/assets/5d341454-81e9-4270-a58c-142c46b4c4b8)
### Вы присылаете .spy в ответ на сообщение пользователя , за которым вы хотите следить 🕵️
###### можно изменить на что-либо не так палевное
![image](https://github.com/user-attachments/assets/a8a522e1-be6a-44ae-b624-1b2b59185c6e)
### И вам в Избранное приходит уведомление о добавлении пользователя в список отслеживания 🔔
![image](https://github.com/user-attachments/assets/3a796a11-c29d-4f54-80e2-d96b15f409c1)
### Туда же отправляются и изменения в сообщении
![image](https://github.com/user-attachments/assets/1294ae1d-2fa6-49cc-90ea-2b1c59993958)
### Работает с фотографиями и видео!

### А самоуничтожающиеся фото сохраняются в Избранном сами :)

## Установка 📂
- Для корректной работы нужен Python 3.13.2 , хотя может работать и на ранних версиях
- `git clone https://github.com/pabcihba/TeleSpy ; pip install telethon; pip install os; pip install json; pip install asyncio`
## Настройка ⚙️
- Перейдите по [этой ссылке](https://my.telegram.org/auth?to=apps) , зарегистрируйтесь , создайте приложение и получите API_ID и API_HASH
- Откройте файл telespy.py и замените API_ID и API_HASH на полученные вами значения
- Введите `cd TeleSpy; python telespy.py` и пройдите регистрацию бота на ваш аккаунт
- **Готово!**
## Запуск 🚀
- `cd TeleSpy; python telespy.py`
# Заключение
Мониторинг изменений/удалений сообщений работает только если скрипт работает на машине с доступом в интернет 24/7 , это может быть какой-то сервер или просто висеть в фоне пока вы работаете , вам решать , куда этот скрипт запихивать  
