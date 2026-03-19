import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import datetime
import json
import os
import time

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

# Хранилище сессий пользователей
user_sessions = {}

# Подключение к VK API
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def get_current_day_key():
    """Возвращает текущий день недели (пн, вт, ...)"""
    days = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    return days[datetime.datetime.today().weekday()]

def send_message(user_id, message, keyboard=None):
    """Отправляет сообщение пользователю"""
    params = {
        'user_id': user_id,
        'message': message,
        'random_id': get_random_id()
    }
    if keyboard:
        params['keyboard'] = json.dumps(keyboard, ensure_ascii=False)
    vk.messages.send(**params)

def send_chat_message(peer_id, message, attachment=None):
    """Отправляет сообщение в беседу"""
    params = {
        'peer_id': peer_id,
        'message': message,
        'random_id': get_random_id()
    }
    if attachment:
        params['attachment'] = attachment
    vk.messages.send(**params)

def get_attachment_from_event(event):
    """Извлекает attachment из события VK"""
    if event.attachments:
        # Берем первое вложение
        att = event.attachments[0]
        
        # Формируем строку attachment в формате VK
        if att['type'] == 'photo':
            photo = att['photo']
            # Формат: photo{owner_id}_{id}
            return f"photo{photo['owner_id']}_{photo['id']}"
        elif att['type'] == 'doc':
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
            color = "secondary"  # серая для выполненных
        else:
            button_text = f"🔴 {task}"
            color = "primary"  # синяя для невыполненных
        
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

# ===== ОСНОВНОЙ ЦИКЛ =====
print(f"Бот запущен. Время: {datetime.datetime.now()}")
print(f"Группа ID: {GROUP_ID}")
print(f"Сотрудники: {EMPLOYEES}")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.strip() if event.text else ""
        
        print(f"Сообщение от {user_id}: {text}")
        print(f"Вложения: {event.attachments}")
        
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
                'before_photo': None
            }
        
        session = user_sessions[user_id]
        
        # Обработка команд
        if text in ["/start", "Начать", "Список заданий"]:
            day_key = get_current_day_key()
            tasks = SCHEDULE.get(day_key, [])
            
            if not tasks:
                send_message(user_id, "🎉 Сегодня выходной! Заданий нет.")
                continue
            
            message = f"📋 Задания на сегодня ({day_key}):\n\n"
            message += "Нажмите на задание, чтобы начать уборку:\n"
            
            # Добавляем список заданий с эмодзи
            for task in tasks:
                if task in session['completed']:
                    message += f"✅ {task}\n"
                else:
                    message += f"🔴 {task}\n"
            
            send_message(user_id, message, create_tasks_keyboard(user_id))
            
        # Обработка нажатий на кнопки с заданиями
        elif text.startswith("🔴") or text.startswith("✅"):
            task_name = text[2:].strip()
            
            # Проверка, не выполнено ли уже задание
            if task_name in session['completed']:
                send_message(user_id, f"✅ Задание '{task_name}' уже выполнено!")
                continue
            
            # Начинаем уборку
            session['current_task'] = task_name
            session['waiting_for'] = 'before'
            session['before_photo'] = None
            
            send_message(user_id, f"📸 Пришлите фото ДО уборки для: '{task_name}'")
            
        # Обработка фото (если есть вложения)
        elif event.attachments:
            # Проверяем, ожидаем ли мы фото
            if not session['waiting_for']:
                send_message(user_id, "❓ Сначала выберите задание из списка.")
                continue
            
            task_name = session['current_task']
            
            # Получаем attachment строку
            attachment = get_attachment_from_event(event)
            
            if not attachment:
                send_message(user_id, "❌ Не удалось обработать фото. Попробуйте еще раз.")
                continue
            
            if session['waiting_for'] == 'before':
                # Сохраняем фото ДО
                session['before_photo'] = attachment
                session['waiting_for'] = 'after'
                send_message(user_id, f"✅ Фото ДО получено. Теперь пришлите фото ПОСЛЕ уборки для '{task_name}'")
                
            elif session['waiting_for'] == 'after':
                # Получили фото ПОСЛЕ - отправляем отчет в беседу
                date_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
                
                # Формируем сообщение для отчета
                report_text = f"✅ ВЫПОЛНЕНО ЗАДАНИЕ:\n"
                report_text += f"📋 {task_name}\n"
                report_text += f"👤 Исполнитель: vk.com/id{user_id}\n"
                report_text += f"📅 Время: {date_str}"
                
                # Отправляем в беседу (если указан REPORT_PEER_ID)
                if REPORT_PEER_ID:
                    # Отправляем оба фото и текст
                    attachments = f"{session['before_photo']},{attachment}"
                    send_chat_message(REPORT_PEER_ID, report_text, attachments)
                
                # Отмечаем задание как выполненное
                session['completed'].append(task_name)
                session['current_task'] = None
                session['waiting_for'] = None
                session['before_photo'] = None
                
                send_message(user_id, f"🎉 Задание '{task_name}' выполнено! Спасибо!")
                
                # Обновляем клавиатуру
                day_key = get_current_day_key()
                tasks = SCHEDULE.get(day_key, [])
                
                if len(session['completed']) == len(tasks):
                    send_message(user_id, "🏆 ПОЗДРАВЛЯЮ! Все задания на сегодня выполнены!")
                else:
                    send_message(user_id, "📋 Продолжаем уборку:", create_tasks_keyboard(user_id))
        
        # Обработка обычного текста
        elif text:
            send_message(user_id, "Используйте кнопки или /start для начала работы.")
