import os
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Telegram API
api_id = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE')

# Каналы
TARGET_CHANNEL = os.getenv('TARGET_CHANNEL')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')

# Лимиты (с преобразованием в числа)
DELAY_BETWEEN_MESSAGES = int(os.getenv('DELAY_BETWEEN_MESSAGES', 300))
MAX_DAILY_MESSAGES = int(os.getenv('MAX_DAILY_MESSAGES', 25))

# Настройки фильтрации (с преобразованием в boolean)
INCLUDE_RECENTLY = os.getenv('INCLUDE_RECENTLY', 'true').lower() == 'true'
INCLUDE_LAST_WEEK = os.getenv('INCLUDE_LAST_WEEK', 'true').lower() == 'true'


# Проверка что все данные есть
def check_config():
    required_vars = ['API_ID', 'API_HASH', 'PHONE', 'TARGET_CHANNEL']
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print("❌ ОШИБКА: Отсутствуют переменные в .env:")
        for var in missing:
            print(f"   - {var}")
        print("\n📝 Скопируй .env.example в .env и заполни своими данными")
        return False
    return True