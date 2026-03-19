import vk_api
import datetime
import sys
import traceback

print("=" * 60)
print("🚀 ТЕСТОВЫЙ БОТ ЗАПУЩЕН")
print(f"📅 Время: {datetime.datetime.now()}")
print("=" * 60)

# ВАШИ ДАННЫЕ - ВСТАВЬТЕ СЮДА!
TOKEN = "vk1.a.8o3iYwN5RhNc73m3oOku_g_o_mFet_eUeLxw"  # ВАШ ТОКЕН
GROUP_ID = 228118061  # ID ВАШЕЙ ГРУППЫ

print(f"🔑 Токен: {TOKEN[:15]}...")
print(f"🏢 Группа ID: {GROUP_ID}")

try:
    # Подключаемся к VK
    print("🔄 Подключаемся к VK API...")
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    
    # Проверяем, что группа существует
    print("🔄 Получаем информацию о группе...")
    group_info = vk.groups.getById(group_id=GROUP_ID)
    print(f"✅ УСПЕХ! Группа: {group_info[0]['name']}")
    
    # Проверяем права токена
    print("🔄 Проверяем права токена...")
    try:
        # Пробуем отправить тестовое сообщение самому себе
        # (замените 552266097 на свой VK ID)
        vk.messages.send(
            user_id=552266097,
            message="✅ Тестовое сообщение от бота!",
            random_id=0
        )
        print("✅ Сообщение отправлено успешно!")
    except Exception as e:
        print(f"❌ Не могу отправить сообщение: {e}")
    
    print("=" * 60)
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ ОШИБКА: {e}")
    traceback.print_exc()

print("🔄 Бот продолжает работу...")
print("Нажмите Ctrl+C для остановки")

# Держим бот запущенным
while True:
    import time
    time.sleep(60)
    print(f"🟢 Бот работает... {datetime.datetime.now().strftime('%H:%M:%S')}")
