import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import datetime
import json
import os
import time
import pickle
import threading
import sys

# ===== НАСТРОЙКИ =====
# Импортируем настройки из отдельного файла
try:
    from config import TOKEN, GROUP_ID, REPORT_PEER_ID, EMPLOYEES, SCHEDULE
except ImportError:
    # Если файла config.py нет, используем значения из переменных окружения
    TOKEN = os.environ.get('VK_TOKEN', '')
    GROUP_ID = int(os.environ.get('VK_GROUP_ID', 0))
    REPORT_PEER_ID = int(os.environ.get('VK_REPORT_PEER_ID', 0))
    EMPLOYEES = [int(id) for id in os.environ.get('VK_EMPLOYEES', '').split(',') if id]
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
SESSION_FILE = '/app/data/user_sessions.pkl'

# ===== ЗАГРУЗКА И СОХРАНЕНИЕ СЕССИЙ =====
def load_sessions():
    """Загружает сессии из файла"""
    try:
        # Создаем директорию, если её нет
        os.makedirs('/app/data', exist_ok=True)
        
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, 'rb') as f:
                return pickle.load(f)
        else:
            print("Файл сессий не найден, создаем новый")
    except Exception as e:
        print(f"Ошибка загрузки сессий: {e}")
    return {}

def save_sessions():
    """Сохраняет сессии в файл"""
    try:
        os.makedirs('/app/data', exist_ok=True)
        with open(SESSION_FILE, 'wb') as f:
            pickle.dump(user_sessions, f)
        print(f"✅ Сессии сохранены. Всего пользователей: {len(user_sessions)}")
    except Exception as e:
        print(f"❌ Ошибка сохранения сессий: {e}")

# Загружаем сессии при старте
user_sessions = load_sessions()
print(f"📂 Загружено сессий: {len(user_sessions)}")

# Запускаем автосохранение в отдельном потоке
def auto_save():
    while True:
        time.sleep(30)  # Сохраняем каждые 30 секунд
        save_sessions()

save_thread = threading.Thread(target=auto_save, daemon=True)
save_thread.start()
print("🔄 Автосохранение запущено")

# ===== ПОДКЛЮЧЕНИЕ К VK =====
print("🔄 Подключаемся к VK API...")
print(f"Токен: {TOKEN[:15]}..." if TOKEN else "❌ Токен не задан!")
print(f"Группа ID: {GROUP_ID}")

try:
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    
    # Проверяем подключение
    group_info = vk.groups.getById(group_id=GROUP_ID)
    print(f"✅ Подключено к группе: {group_info[0]['name']}")
    
    longpoll = VkLongPoll(vk_session)
    print("✅ LongPoll запущен")
    print("👂 Ожидаем сообщения...")
    
except Exception as e:
    print(f"❌ Ошибка подключения к VK: {e}")
    sys.exit(1)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def get_current_day_key():
    """Возвращает текущий день недели (пн, вт, ...)"""
    days = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    return days[datetime.datetime.today().weekday()]

def send_message(user_id, message, keyboard=None):
    """Отправляет сообщение пользователю"""
    try:
        params = {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id()
        }
        if keyboard:
            params['keyboard'] = json.dumps(keyboard, ensure_ascii=False)
        vk.messages.send(**params)
        print(f"✅ Отправлено пользователю {user_id}: {message[:30]}...")
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")

def send_chat_message(peer_id, message, attachment=None):
    """Отправляет сообщение в беседу"""
    try:
        params = {
            'peer_id': peer_id,
            'message': message,
            'random_id': get_random_id()
        }
        if attachment:
            params['attachment'] = attachment
        vk.messages.send(**params)
        print(f"✅ Отправлено в беседу {peer_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки в беседу: {e}")

def get_attachment_from_event(event):
    """Извлекает attachment из события VK"""
    if event.attachments:
        att = event.attachments[0]
        if att['type'] == 'photo':
            photo = att['photo']
            return f"photo{photo['owner_id']}_{photo['id']}"
        elif att['type'] == 'doc' and att['doc']['ext'] in ['jpg', 'jpeg', 'png', 'gif']:
            doc = att['doc']
            return f"doc{doc['owner_id']}_{doc['id']}"
    return None

def create_tasks_keyboard(user_id):
    """Создает клавиатуру с заданиями"""
    day_key = get_current_day_key()
    tasks = SCHEDULE.get(day_key, [])
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'completed': [],
            'current_task': None,
            'waiting_for': None,
            'before_photo': None
        }
    
    completed = user_sessions[user_id]['completed']
    
    # Создаем клавиатуру
    keyboard = {
        "one_time": False,
        "buttons": []
    }
    
    # Добавляем кнопки для каждого задания
    row = []
    for i, task in enumerate(tasks):
        if task in completed:
            button_text = f"✅ {task}"
            color = "secondary"
        else:
            button_text = f"🔴 {task}"
            color = "primary"
        
        row.append({
            "action": {
                "type": "text",
                "label": button_text,
                "payload": json.dumps({"task": task})
            },
            "color": color
        })
        
        # По 2 кнопки в ряд
        if len(row) == 2 or i == len(tasks) - 1:
            keyboard["buttons"].append(row)
            row = []
    
    return keyboard

def reset_old_sessions():
    """Сбрасывает сессии в начале нового дня"""
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
                user_sessions[user_id]['before_photo'] = None
                user_sessions[user_id]['last_reset'] = datetime.datetime.now().isoformat()
                print(f"🔄 Сброс сессии пользователя {user_id} для нового дня")

# Сбрасываем старые сессии при старте
reset_old_sessions()

# ===== ОСНОВНОЙ ЦИКЛ =====
print("=" * 50)
print("🚀 БОТ ЗАПУЩЕН")
print(f"📅 Время: {datetime.datetime.now()}")
print(f"👥 Сотрудники: {EMPLOYEES}")
print("=" * 50)

while True:
    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                user_id = event.user_id
                text = event.text.strip() if event.text else ""
                
                print(f"\n📩 [{datetime.datetime.now().strftime('%H:%M:%S')}] Сообщение от {user_id}: '{text}'")
                if event.attachments:
                    print(f"   📎 Вложений: {len(event.attachments)}")
                
                # Проверка, является ли пользователь сотрудником
                if user_id not in EMPLOYEES:
                    send_message(user_id, "❌ Это бот для сотрудников. Обратитесь к администратору.")
                    continue
                
                # Инициализация сессии пользователя
                if user_id not in user_sessions:
                    user_sessions[user_id] = {
                        'completed': [],
                        'current_task': None,
                        'waiting_for': None,
                        'before_photo': None,
                        'last_reset': datetime.datetime.now().isoformat()
                    }
                    save_sessions()
                
                session = user_sessions[user_id]
                
                # 1. Обработка фото (самый приоритет)
                if event.attachments:
                    # Получаем attachment
                    attachment = get_attachment_from_event(event)
                    
                    if not attachment:
                        send_message(user_id, "❌ Не удалось обработать фото. Попробуйте еще раз.")
                        continue
                    
                    # Проверяем, ожидаем ли мы фото
                    if not session['waiting_for']:
                        send_message(user_id, "❓ Сначала выберите задание из списка.")
                        continue
                    
                    task_name = session['current_task']
                    if not task_name:
                        send_message(user_id, "❓ Ошибка: не выбрано задание. Нажмите /start")
                        session['waiting_for'] = None
                        save_sessions()
                        continue
                    
                    if session['waiting_for'] == 'before':
                        # Сохраняем фото ДО
                        session['before_photo'] = attachment
                        session['waiting_for'] = 'after'
                        save_sessions()
                        
                        send_message(user_id, f"✅ Фото ДО получено. Теперь пришлите фото ПОСЛЕ уборки для '{task_name}'")
                        
                    elif session['waiting_for'] == 'after':
                        # Получили фото ПОСЛЕ - отправляем отчет
                        date_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
                        
                        # Формируем сообщение для отчета
                        report_text = f"✅ ВЫПОЛНЕНО ЗАДАНИЕ:\n"
                        report_text += f"📋 {task_name}\n"
                        report_text += f"👤 Исполнитель: vk.com/id{user_id}\n"
                        report_text += f"📅 Время: {date_str}"
                        
                        # Отправляем в беседу (если указан REPORT_PEER_ID)
                        if REPORT_PEER_ID and REPORT_PEER_ID > 0:
                            attachments = f"{session['before_photo']},{attachment}"
                            send_chat_message(REPORT_PEER_ID, report_text, attachments)
                        
                        # Отмечаем задание как выполненное
                        session['completed'].append(task_name)
                        session['current_task'] = None
                        session['waiting_for'] = None
                        session['before_photo'] = None
                        save_sessions()
                        
                        send_message(user_id, f"🎉 Задание '{task_name}' выполнено! Спасибо!")
                        
                        # Обновляем клавиатуру
                        day_key = get_current_day_key()
                        tasks = SCHEDULE.get(day_key, [])
                        
                        if len(session['completed']) == len(tasks):
                            send_message(user_id, "🏆 ПОЗДРАВЛЯЮ! Все задания на сегодня выполнены!")
                        else:
                            send_message(user_id, "📋 Продолжаем уборку:", create_tasks_keyboard(user_id))
                
                # 2. Обработка команд
                elif text in ["/start", "Начать", "Список заданий"]:
                    day_key = get_current_day_key()
                    tasks = SCHEDULE.get(day_key, [])
                    
                    if not tasks:
                        send_message(user_id, "🎉 Сегодня выходной! Заданий нет.")
                        continue
                    
                    message = f"📋 Задания на сегодня ({day_key}):\n\n"
                    message += "Нажмите на задание, чтобы начать уборку:\n"
                    
                    for task in tasks:
                        if task in session['completed']:
                            message += f"✅ {task}\n"
                        else:
                            message += f"🔴 {task}\n"
                    
                    send_message(user_id, message, create_tasks_keyboard(user_id))
                
                # 3. Обработка нажатий на кнопки
                elif text.startswith("🔴") or text.startswith("✅"):
                    task_name = text[2:].strip()
                    
                    # Проверка, не выполнено ли уже задание
                    if task_name in session['completed']:
                        send_message(user_id, f"✅ Задание '{task_name}' уже выполнено!")
                        continue
                    
                    # Проверяем, есть ли такое задание в расписании
                    day_key = get_current_day_key()
                    tasks = SCHEDULE.get(day_key, [])
                    
                    if task_name not in tasks:
                        send_message(user_id, f"❌ Задание '{task_name}' не найдено в расписании на сегодня.")
                        continue
                    
                    # Начинаем уборку
                    session['current_task'] = task_name
                    session['waiting_for'] = 'before'
                    session['before_photo'] = None
                    save_sessions()
                    
                    send_message(user_id, f"📸 Пришлите фото ДО уборки для: '{task_name}'")
                
                # 4. Обработка неизвестных команд
                elif text:
                    send_message(user_id, "Используйте кнопки или /start для начала работы.")
    
    except Exception as e:
        print(f"❌ Ошибка в основном цикле: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(5)  # Пауза перед перезапуском
