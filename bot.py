import telebot
from telebot import types
import datetime
import time
import os
import json
import pickle

# ===== НАСТРОЙКИ =====
try:
    from config import TOKEN, REPORT_CHAT_ID, EMPLOYEES, SCHEDULE
except ImportError:
    TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
    REPORT_CHAT_ID = int(os.environ.get('REPORT_CHAT_ID', 0))
    EMPLOYEES = [int(id) for id in os.environ.get('EMPLOYEES', '').split(',') if id]
    SCHEDULE = {
        "пн": ["Огнетушители", "Тележки", "Коробки", "Ножи и столики"],
        "вт": ["Вентиляция", "Электрощитки", "Складские стеллажи"],
        "ср": ["Сантехника", "Мусорные баки", "Полы в цехе"],
        "чт": ["Окна", "Освещение", "Двери и ручки"],
        "пт": ["Инвентарь", "Раковины", "Стены"],
        "сб": ["Генеральная склада"],
        "вс": []
    }

# Файл для хранения сессий
SESSION_FILE = '/app/data/sessions.pkl'

# ===== ЗАГРУЗКА И СОХРАНЕНИЕ СЕССИЙ =====
def load_sessions():
    try:
        os.makedirs('/app/data', exist_ok=True)
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Ошибка загрузки сессий: {e}")
    return {}

def save_sessions():
    try:
        os.makedirs('/app/data', exist_ok=True)
        with open(SESSION_FILE, 'wb') as f:
            pickle.dump(user_sessions, f)
        print(f"✅ Сессии сохранены ({len(user_sessions)} пользователей)")
    except Exception as e:
        print(f"Ошибка сохранения сессий: {e}")

# Загружаем сессии
user_sessions = load_sessions()
print(f"📂 Загружено сессий: {len(user_sessions)}")

# Создаем бота
bot = telebot.TeleBot(TOKEN)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def get_current_day_key():
    days = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    return days[datetime.datetime.today().weekday()]

def create_tasks_keyboard(user_id):
    day_key = get_current_day_key()
    tasks = SCHEDULE.get(day_key, [])
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'completed': [],
            'current_task': None,
            'waiting_for': None,
            'before_photo_id': None
        }
    
    completed = user_sessions[user_id]['completed']
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    for task in tasks:
        if task in completed:
            button_text = f"✅ {task}"
        else:
            button_text = f"🔴 {task}"
        buttons.append(types.InlineKeyboardButton(button_text, callback_data=f"task_{task}"))
    
    keyboard.add(*buttons)
    return keyboard

def reset_old_sessions():
    """Сбрасывает выполненные задания в новом дне"""
    today = datetime.datetime.now().date()
    for user_id in list(user_sessions.keys()):
        if 'last_reset' not in user_sessions[user_id]:
            user_sessions[user_id]['last_reset'] = datetime.datetime.now().isoformat()
        else:
            last_reset = datetime.datetime.fromisoformat(user_sessions[user_id]['last_reset']).date()
            if last_reset != today:
                user_sessions[user_id]['completed'] = []
                user_sessions[user_id]['current_task'] = None
                user_sessions[user_id]['waiting_for'] = None
                user_sessions[user_id]['before_photo_id'] = None
                user_sessions[user_id]['last_reset'] = datetime.datetime.now().isoformat()
                print(f"🔄 Сброс сессии пользователя {user_id} для нового дня")

# Сбрасываем при старте
reset_old_sessions()

# ===== ОБРАБОТЧИКИ =====

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    # Проверка сотрудника
    if user_id not in EMPLOYEES:
        bot.reply_to(message, "❌ Это бот для сотрудников. Обратитесь к администратору.")
        return
    
    day_key = get_current_day_key()
    tasks = SCHEDULE.get(day_key, [])
    
    if not tasks:
        bot.reply_to(message, "🎉 Сегодня выходной! Заданий нет.")
        return
    
    # Инициализация сессии
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'completed': [],
            'current_task': None,
            'waiting_for': None,
            'before_photo_id': None,
            'last_reset': datetime.datetime.now().isoformat()
        }
        save_sessions()
    
    text = f"📋 *Задания на сегодня ({day_key}):*\n\n"
    text += "Нажмите на задание, чтобы начать уборку:\n"
    
    bot.send_message(
        user_id, 
        text,
        reply_markup=create_tasks_keyboard(user_id),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if user_id not in user_sessions:
        bot.answer_callback_query(call.id, "❓ Нажмите /start для начала")
        return
    
    session = user_sessions[user_id]
    
    if data.startswith("task_"):
        task_name = data.replace("task_", "")
        
        # Проверка выполнения
        if task_name in session['completed']:
            bot.answer_callback_query(call.id, f"✅ Задание уже выполнено!")
            return
        
        # Проверка расписания
        day_key = get_current_day_key()
        tasks = SCHEDULE.get(day_key, [])
        if task_name not in tasks:
            bot.answer_callback_query(call.id, f"❌ Задание не найдено в расписании")
            return
        
        # Начинаем уборку
        session['current_task'] = task_name
        session['waiting_for'] = 'before'
        save_sessions()
        
        bot.edit_message_text(
            f"📸 Пришлите *фото ДО* уборки для: *{task_name}*",
            user_id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        bot.reply_to(message, "❓ Сначала нажмите /start")
        return
    
    session = user_sessions[user_id]
    
    if not session['waiting_for']:
        bot.reply_to(message, "❓ Сначала выберите задание из списка.")
        return
    
    task_name = session['current_task']
    if not task_name:
        bot.reply_to(message, "❓ Ошибка: не выбрано задание. Нажмите /start")
        session['waiting_for'] = None
        save_sessions()
        return
    
    # Получаем file_id фото
    file_id = message.photo[-1].file_id
    
    if session['waiting_for'] == 'before':
        # Сохраняем фото ДО
        session['before_photo_id'] = file_id
        session['waiting_for'] = 'after'
        save_sessions()
        
        bot.reply_to(message, f"✅ Фото ДО получено. Теперь пришлите *фото ПОСЛЕ* уборки для: *{task_name}*", parse_mode="Markdown")
        
    elif session['waiting_for'] == 'after':
        # Получили фото ПОСЛЕ - отправляем отчет
        date_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        user_name = message.from_user.first_name or "Сотрудник"
        
        # Отправляем фото в группу отчетов
        if REPORT_CHAT_ID:
            try:
                # Отправляем фото ДО
                bot.send_photo(
                    REPORT_CHAT_ID,
                    session['before_photo_id'],
                    caption=f"📸 *Фото ДО:* {task_name}",
                    parse_mode="Markdown"
                )
                
                # Отправляем фото ПОСЛЕ
                bot.send_photo(
                    REPORT_CHAT_ID,
                    file_id,
                    caption=f"📸 *Фото ПОСЛЕ:* {task_name}",
                    parse_mode="Markdown"
                )
                
                # Отправляем текстовый отчет
                report_text = f"✅ *ВЫПОЛНЕНО ЗАДАНИЕ:*\n"
                report_text += f"📋 *{task_name}*\n"
                report_text += f"👤 *Исполнитель:* {user_name}\n"
                report_text += f"📅 *Время:* {date_str}"
                
                bot.send_message(REPORT_CHAT_ID, report_text, parse_mode="Markdown")
                print(f"✅ Отчет отправлен в группу {REPORT_CHAT_ID}")
            except Exception as e:
                print(f"❌ Ошибка отправки отчета: {e}")
        
        # Отмечаем задание как выполненное
        session['completed'].append(task_name)
        session['current_task'] = None
        session['waiting_for'] = None
        session['before_photo_id'] = None
        save_sessions()
        
        bot.reply_to(message, f"🎉 Задание *{task_name}* выполнено! Спасибо!", parse_mode="Markdown")
        
        # Проверяем, все ли задания выполнены
        day_key = get_current_day_key()
        tasks = SCHEDULE.get(day_key, [])
        
        if len(session['completed']) == len(tasks):
            bot.send_message(user_id, "🏆 *ПОЗДРАВЛЯЮ!* Все задания на сегодня выполнены!", parse_mode="Markdown")
        else:
            # Отправляем обновленный список
            text = f"📋 *Продолжаем уборку:*"
            bot.send_message(
                user_id, 
                text, 
                reply_markup=create_tasks_keyboard(user_id), 
                parse_mode="Markdown"
            )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    
    if message.text == "/start":
        return
    
    if user_id not in EMPLOYEES:
        bot.reply_to(message, "❌ Это бот для сотрудников.")
        return
    
    bot.reply_to(message, "Используйте кнопки или /start для начала работы.")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 TELEGRAM БОТ ЗАПУЩЕН")
    print(f"📅 Время: {datetime.datetime.now()}")
    print(f"👥 Сотрудники: {EMPLOYEES}")
    print(f"📢 Группа отчетов: {REPORT_CHAT_ID}")
    print("=" * 50)
    
    # Бесконечный цикл с автосохранением
    last_save = time.time()
    
    while True:
        try:
            # Запускаем бота
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
        
        # Сохраняем сессии каждые 60 секунд
        if time.time() - last_save > 60:
            save_sessions()
            last_save = time.time()
