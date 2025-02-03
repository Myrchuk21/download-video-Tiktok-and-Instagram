#!/usr/bin/env python3
from os import remove
import sys
from time import sleep, time
import telebot
import yt_dlp
import datetime
from telebot import types
from pymongo import MongoClient

# Подключение к MongoDB
client = MongoClient('ur base link')  # Используйте ваш URL, если MongoDB находится на другом хосте или порту
db = client['ur user name']  # Создаем/подключаемся к базе данных
statistics_collection = db['ur base name']  # Коллекция для хранения статистики

def help():
    print('Create bot in https://t.me/BotFather and put token to script or with -t argument')
    print('-t <token_string> - puts telegram bot token to script')

token = 'bot token'

user_chats = set()  # Список всех пользователей, с кем бот взаимодействовал
whitelist = {123456789, 5941001171}  # ID пользователей, которые могут отключать рекламу и смотреть статистику
hide_advert_users = set()
advert_disabled_for_all = False  # Флаг, который указывает, что реклама отключена для всех пользователей

# Словарь для хранения времени последнего сообщения пользователя
user_last_message_time = {}

# Тайм-аут в 5 секунд для антиспама
SPAM_TIMEOUT = 5

# Глобальная переменная counter
counter = 0

# Словарь для хранения языка пользователей
user_language = {}

# Статистика скачанных видео
video_downloads = []  # Список всех скачанных видео (время скачивания)
user_ids = set()  # Множество уникальных пользователей, которые взаимодействовали с ботом
service_stats = {"tiktok": 0, "instagram": 0}  # Статистика по сервисам

argIdx = 1
while argIdx < len(sys.argv):
    if sys.argv[argIdx] == '-t':
        if argIdx + 1 >= len(sys.argv):
            print('Token expected after -t')
            quit()
        else:
            token = sys.argv[argIdx + 1]
            argIdx += 1
    elif sys.argv[argIdx] == '-h':
        help()
        quit()
    else:
        print('{} - unknown arg'.format(sys.argv[argIdx]))
        help()
        quit()
    argIdx += 1

bot = telebot.TeleBot(token)

with open('log.txt', 'a') as f:
    f.write("launched {}\n".format(datetime.datetime.now()))

# Функция для создания кнопок выбора языка
def language_buttons():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_ru = types.KeyboardButton("Русский")
    button_en = types.KeyboardButton("English")
    keyboard.add(button_ru, button_en)
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    # Если язык не был выбран ранее, предложим выбрать язык
    if message.from_user.id not in user_language:
        bot.send_message(message.from_user.id, "Привет! Выберите язык / Hello! Choose a language:", reply_markup=language_buttons())
    else:
        # Если язык был выбран, покажем сообщение на выбранном языке
        lang = user_language[message.from_user.id]
        if lang == "ru":
            bot.send_message(message.from_user.id, "🚩 Привет, этот бот может скачивать видео без водяного знака с 𝐓𝐢𝐤𝐓𝐨𝐤 и Instagram Reels. Для начала, отправь ссылку на видео")
        else:
            bot.send_message(message.from_user.id, "🚩 Hello, this bot can download videos without watermark from TikTok and Instagram Reels. To get started, send a video link")

# Команда для смены языка
@bot.message_handler(commands=['lang'])
def lang(message):
    # Отправляем клавиатуру для выбора языка
    bot.send_message(message.from_user.id, "Выберите язык / Choose a language:", reply_markup=language_buttons())

@bot.message_handler(func=lambda message: message.text in ["Русский", "English"])
def set_language(message):
    # Сохраняем выбранный язык
    if message.text == "Русский":
        user_language[message.from_user.id] = "ru"
        bot.send_message(message.from_user.id, "Язык изменён на русский. 🚩 Теперь отправляйте ссылку на видео.", reply_markup=types.ReplyKeyboardRemove())
    elif message.text == "English":
        user_language[message.from_user.id] = "en"
        bot.send_message(message.from_user.id, "Language changed to English. 🚩 Now send a video link.", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['off-advert'])
def hide_advert_all(message):
    if message.from_user.id in whitelist:
        global advert_disabled_for_all
        advert_disabled_for_all = True  # Отключаем рекламу для всех
        bot.send_message(message.chat.id, "✅ Реклама отключена для всех пользователей.")
    else:
        bot.send_message(message.chat.id, "❌ У вас нет прав для использования этой команды.")

@bot.message_handler(commands=['on-advert'])
def hide_advert_all(message):
    if message.from_user.id in whitelist:
        global advert_disabled_for_all
        advert_disabled_for_all = False  # Включает рекламу для всех
        bot.send_message(message.chat.id, "✅ Реклама включена для всех пользователей.")
    else:
        bot.send_message(message.chat.id, "❌ У вас нет прав для использования этой команды.")

# Команда для просмотра статистики
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id not in whitelist:
        bot.send_message(message.chat.id, "❌ У вас нет прав для просмотра статистики.")
        return
    
    # Извлекаем статистику из MongoDB
    stats = statistics_collection.find_one({"_id": "statistics"})
    
    if stats:
        total_downloads = stats.get("total_downloads", 0)
        total_users = stats.get("total_users", 0)
        tiktok_downloads = stats.get("tiktok", 0)
        instagram_downloads = stats.get("instagram", 0)
    else:
        total_downloads = 0
        total_users = 0
        tiktok_downloads = 0
        instagram_downloads = 0
    
    # Формируем сообщение
    response = (
        f"📊 Статистика бота:\n\n"
        f"Общее количество скачанных видео: {total_downloads}\n"
        f"Количество уникальных пользователей: {total_users}\n\n"
        f"📱 Скачано с TikTok: {tiktok_downloads} видео\n"
        f"📸 Скачано с Instagram: {instagram_downloads} видео\n"
    )
    bot.send_message(message.chat.id, response)

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    global counter
    user_chats.add(message.chat.id)

    # Проверяем, прошло ли достаточно времени с последнего сообщения пользователя
    current_time = time()
    last_message_time = user_last_message_time.get(message.from_user.id, 0)
    
    if current_time - last_message_time < SPAM_TIMEOUT:
        bot.send_message(message.from_user.id, " ❌ ")
        return

    # Обновляем время последнего сообщения пользователя
    user_last_message_time[message.from_user.id] = current_time
    
    # Проверяем язык пользователя
    lang = user_language.get(message.from_user.id, "ru")  # Если язык не выбран, по умолчанию русский
    
    if message.text == '/start' or message.text == '/help':
        if lang == "ru":
            bot.send_message(message.from_user.id, '🚩 Привет, этот бот может скачивать видео без водяного знака с 𝐓𝐢𝐤𝐓𝐨𝐤 и Instagram Reels. Для начала, отправь ссылку на видео')
        else:
            bot.send_message(message.from_user.id, '🚩 Hello, this bot can download videos without watermark from TikTok and Instagram Reels. To get started, send a video link')

    elif 'tiktok.com' in message.text:
        counter += 1
        current_counter = counter
        service_stats["tiktok"] += 1  # Увеличиваем счетчик скачиваний с TikTok

        try:
            print('{} Загружаю: {}'.format(current_counter, message.text))
            status_message = bot.send_message(message.from_user.id, ' ⌛ ')

            video_filename = 'video{}.mp4'.format(current_counter)
            try:
                bot.edit_message_text(' 🚀 ', message.from_user.id, status_message.message_id)
                yt_dlp.YoutubeDL({
                    'quiet': True,
                    'outtmpl': video_filename
                }).download([message.text])
                bot.edit_message_text(' ✅ ', message.from_user.id, status_message.message_id)
            except:
                with open('log.txt', 'a') as f:
                    f.write("{} Ошибка загрузки от {}: {}\n".format(current_counter, message.from_user.id, message.text))
                bot.edit_message_text('❌ Ошибка загрузки', message.from_user.id, status_message.message_id)
                return

            caption = f'🎥 [Оригинальное видео]({message.text})\n[@tttsavebot](https://t.me/tttsavebot_bot)'
            bot.send_video(message.from_user.id, video=open(video_filename, 'rb'), caption=caption, parse_mode='Markdown')
            print('{} Отправлено: {}'.format(current_counter, message.text))

            # Записываем время загрузки видео
            video_downloads.append(datetime.datetime.now())
            user_ids.add(message.from_user.id)  # Добавляем пользователя в список уникальных пользователей
            
            # Обновляем статистику в MongoDB
            statistics_collection.update_one(
                {"_id": "statistics"},
                {"$inc": {"total_downloads": 1, "total_users": 1, "tiktok": 1}},
                upsert=True
            )
            
            # Отправка рекламы, если реклама не отключена для всех или если пользователь не отключил её для себя
            if not advert_disabled_for_all and message.from_user.id not in hide_advert_users:
                if lang == "ru":
                    bot.send_message(message.chat.id, "📢 Реклама: хотите приобрести рекламу?! Обратитесь к Админу")
                else:
                    bot.send_message(message.chat.id, "📢 Advertisement: want to buy ads?! Contact Admin")
            
            remove(video_filename)
            with open('log.txt', 'a') as f:
                f.write("{} Успешно загружено от {}: {}\n".format(current_counter, message.from_user.id, message.text))
        except:
            with open('log.txt', 'a') as f:
                f.write("{} Ошибка бота {}: {}\n".format(current_counter, message.from_user.id, message.text))
            print('Ошибка бота')

    elif 'instagram.com/reel' in message.text:
        counter += 1
        current_counter = counter
        service_stats["instagram"] += 1  # Увеличиваем счетчик скачиваний с Instagram

        try:
            print('{} Загружаю: {}'.format(current_counter, message.text))
            status_message = bot.send_message(message.from_user.id, ' ⌛ ')

            video_filename = 'video{}.mp4'.format(current_counter)
            try:
                bot.edit_message_text(' 🚀 ', message.from_user.id, status_message.message_id)
                yt_dlp.YoutubeDL({
                    'quiet': True,
                    'outtmpl': video_filename
                }).download([message.text])
                bot.edit_message_text(' ✅ ', message.from_user.id, status_message.message_id)
            except:
                with open('log.txt', 'a') as f:
                    f.write("{} Ошибка загрузки от {}: {}\n".format(current_counter, message.from_user.id, message.text))
                bot.edit_message_text('❌ Ошибка загрузки', message.from_user.id, status_message.message_id)
                return

            caption = f'🎥 [Оригинальное видео]({message.text})\n[@tttsavebot](https://t.me/tttsavebot_bot)'
            bot.send_video(message.from_user.id, video=open(video_filename, 'rb'), caption=caption, parse_mode='Markdown')
            print('{} Отправлено: {}'.format(current_counter, message.text))

            # Записываем время загрузки видео
            video_downloads.append(datetime.datetime.now())
            user_ids.add(message.from_user.id)  # Добавляем пользователя в список уникальных пользователей
            
            # Обновляем статистику в MongoDB
            statistics_collection.update_one(
                {"_id": "statistics"},
                {"$inc": {"total_downloads": 1, "total_users": 1, "instagram": 1}},
                upsert=True
            )
            
            # Отправка рекламы, если реклама не отключена для всех или если пользователь не отключил её для себя
            if not advert_disabled_for_all and message.from_user.id not in hide_advert_users:
                if lang == "ru":
                    bot.send_message(message.chat.id, "📢 Реклама: хотите приобрести рекламу?! Обратитесь к Админу")
                else:
                    bot.send_message(message.chat.id, "📢 Advertisement: want to buy ads?! Contact Admin")
            
            remove(video_filename)
            with open('log.txt', 'a') as f:
                f.write("{} Успешно загружено от {}: {}\n".format(current_counter, message.from_user.id, message.text))
        except:
            with open('log.txt', 'a') as f:
                f.write("{} Ошибка бота {}: {}\n".format(current_counter, message.from_user.id, message.text))
            print('Ошибка бота')

    else:
        if lang == "ru":
            bot.send_message(message.from_user.id, '❌ Принимаются только ссылки на TikTok или Instagram Reels')
        else:
            bot.send_message(message.from_user.id, '❌ Only TikTok or Instagram Reels links are accepted')

while True:
    try:
        bot.polling(none_stop=True, interval=0)
    except:
        print('Ошибка работы бота. Перезапуск...')
        sleep(15)