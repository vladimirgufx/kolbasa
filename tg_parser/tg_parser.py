import asyncio
import sys
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import UserStatusOnline, UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth
from config import (
    api_id, API_HASH, PHONE, TARGET_CHANNEL, ADMIN_USERNAME,
    DELAY_BETWEEN_MESSAGES, MAX_DAILY_MESSAGES,
    INCLUDE_RECENTLY, INCLUDE_LAST_WEEK, check_config
)

# ВАРИАНТЫ ПЕРВОГО СООБЩЕНИЯ
FIRST_MESSAGES_RU = [
    "сап бро, тебе нужен промик на заказ на пойзоне?",
    "ку бро, тебе нужен промик на заказ на пойзоне?",
    "здаров бро, тебе нужен промик на заказ на пойзоне?",
    "превет, тебе нужен промик на заказ на пойзоне?",
    "привет, тебе нужен промик на заказ на пойзоне?"
]

FIRST_MESSAGES_EN = [
    "сaп брo, тебe нужeн прoмик на зaкaз на пoйзoне?",
    "ку брo, тeбe нужeн прoмик нa закaз нa пoйзoне?",
    "здарoв брo, тебe нужeн промик нa закaз нa пoйзoнe?",
    "прeвeт, тeбe нужeн прoмик на зaказ на пoйзоне?",
    "привeт, тебe нужeн промик на закaз нa пoйзоне?"
]

# ВАРИАНТЫ ВТОРОГО СООБЩЕНИЯ
SECOND_MESSAGES_RU = [
    "я просто в канале @PoizonCountry выиграл, бесплатно отдам ес че",
    "я прост в канале @PoizonCountry выиграл, бесплатно отдам если че",
    "я прост в канале @PoizonCountry выиграл, отдам бесплатно ес че",
    "я проста в канале @PoizonCountry выиграл, бесплатно отдам есле что"
]

SECOND_MESSAGES_EN = [
    "я прoстo в кaнaлe @PoizonCountry выигрaл, бeсплaтнo oтдaм eс чe",
    "я прoст в кaнале @PoizonCountry выигрaл, бeсплатно отдaм если чe",
    "я прoст в кaнaле @PoizonCountry выигрaл, oтдaм бeсплaтно ec чe",
    "я простa в кaнале @PoizonCountry выиграл, бесплaтно отдaм eслe что"
]

# Файлы
PROCESSED_USERS_FILE = 'processed_users.txt'
SESSION_FILE = 'session_name'
FORWARD_COUNTER_FILE = 'forward_counter.txt'
SPAM_CHECK_FILE = 'spam_check.txt'
STATS_FILE = 'stats.txt'
# =============================================

client = TelegramClient(SESSION_FILE, api_id, API_HASH)

if not check_config():
    exit(1)

client = TelegramClient('session_name', int(api_id), API_HASH)

# Глобальные переменные
spam_blocked = False
last_successful_send = datetime.now()
consecutive_failures = 0
MAX_CONSECUTIVE_FAILURES = 3

# Статистика
stats = {
    'total_checked': 0,
    'online_skipped': 0,
    'offline_found': 0,
    'sent_count': 0,
    'start_time': None
}


def load_processed_users():
    try:
        with open(PROCESSED_USERS_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()


def save_processed_user(user_id):
    with open(PROCESSED_USERS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{user_id}\n")


def load_forward_counter():
    try:
        with open(FORWARD_COUNTER_FILE, 'r', encoding='utf-8') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def save_forward_counter(counter):
    with open(FORWARD_COUNTER_FILE, 'w', encoding='utf-8') as f:
        f.write(str(counter))


def load_spam_status():
    try:
        with open(SPAM_CHECK_FILE, 'r', encoding='utf-8') as f:
            data = f.read().strip()
            if data:
                return data == 'True'
    except FileNotFoundError:
        pass
    return False


def save_spam_status(is_blocked):
    with open(SPAM_CHECK_FILE, 'w', encoding='utf-8') as f:
        f.write(str(is_blocked))


def save_stats():
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            f.write(f"Всего проверено: {stats['total_checked']}\n")
            f.write(f"Онлайн (пропущено): {stats['online_skipped']}\n")
            f.write(f"Офлайн (найдено): {stats['offline_found']}\n")
            f.write(f"Отправлено: {stats['sent_count']}\n")
            if stats['start_time']:
                elapsed = time.time() - stats['start_time']
                f.write(f"Время работы: {str(timedelta(seconds=int(elapsed)))}\n")
    except:
        pass


def get_random_message(message_list_ru, message_list_en):
    if random.random() < 0.7:
        return random.choice(message_list_ru)
    else:
        return random.choice(message_list_en)


def is_user_offline(user):
    """Быстрая проверка статуса"""
    status = user.status

    if status is None:
        return True

    if isinstance(status, UserStatusOnline):
        return False

    if isinstance(status, UserStatusOffline):
        return True

    if isinstance(status, UserStatusRecently):
        return INCLUDE_RECENTLY

    if isinstance(status, UserStatusLastWeek):
        return INCLUDE_LAST_WEEK

    return True


def print_status(current, total, user=None, action=None):
    """Красивый статус в одну строку"""
    elapsed = time.time() - stats['start_time'] if stats['start_time'] else 0
    elapsed_str = str(timedelta(seconds=int(elapsed)))

    if action == "found" and user:
        status_line = f"\r✅ НАШЕЛ ОФЛАЙН: @{user.username:<15} | Отправлено: {stats['sent_count']}/{MAX_DAILY_MESSAGES} | Время: {elapsed_str}"
    elif action == "skip" and user:
        status_line = f"\r⏭️ ПРОПУСТИЛ ОНЛАЙН: @{user.username:<15} | Всего проверено: {current}/{total} | Время: {elapsed_str}"
    else:
        percent = current / total if total > 0 else 0
        bar_length = 20
        arrow = '█' * int(round(percent * bar_length))
        spaces = '░' * (bar_length - len(arrow))

        status_line = f"\r[{arrow}{spaces}] {percent:.1%} | Проверено: {current}/{total} | Офлайн: {stats['offline_found']} | Отправлено: {stats['sent_count']} | Время: {elapsed_str}"

    sys.stdout.write(status_line)
    sys.stdout.flush()


async def check_spam_block():
    global spam_blocked, last_successful_send, consecutive_failures

    try:
        me = await client.get_me()
        test_text = f"spam_test_{random.randint(1000, 9999)}"
        await client.send_message(me.id, test_text)

        await asyncio.sleep(2)

        messages = await client.get_messages(me.id, limit=5)

        found = False
        for msg in messages:
            if msg.text and msg.text == test_text:
                found = True
                await client.delete_messages(me.id, msg.id)
                break

        if found:
            if spam_blocked:
                print("\n✅ СПАМ-БЛОК СНЯТ!")
                spam_blocked = False
                consecutive_failures = 0
                last_successful_send = datetime.now()
                save_spam_status(False)
            return True
        else:
            consecutive_failures += 1
            print(f"\n❌ Тестовое сообщение не найдено. Попытка {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES and not spam_blocked:
                print("\n⚠️  ОБНАРУЖЕН СПАМ-БЛОК!")
                spam_blocked = True
                save_spam_status(True)
            return False

    except FloodWaitError as e:
        print(f"\n⏳ Флуд контроль: {e.seconds}с")
        return True
    except Exception as e:
        print(f"\n❌ Ошибка проверки: {e}")
        consecutive_failures += 1
        return False


async def wait_if_spam_blocked():
    global spam_blocked

    if not spam_blocked:
        return True

    print("\n" + "=" * 50)
    print("⚠️  АККАУНТ В СПАМ-БЛОКЕ")
    print("=" * 50)
    print("💤 Режим ожидания, проверка каждые 30 минут...")

    while spam_blocked:
        await asyncio.sleep(30 * 60)  # 30 минут
        print("\n🔄 Проверка статуса...")
        await check_spam_block()

    print("\n✅ Аккаунт разблокирован, продолжаем!")
    return True


async def safe_send_message(user_entity, text):
    global spam_blocked, last_successful_send, consecutive_failures

    if spam_blocked:
        return False

    try:
        await client.send_message(user_entity, text)
        last_successful_send = datetime.now()
        consecutive_failures = 0
        return True
    except FloodWaitError as e:
        print(f"\n⏳ Флуд {e.seconds}с")
        await asyncio.sleep(e.seconds)
        try:
            await client.send_message(user_entity, text)
            last_successful_send = datetime.now()
            consecutive_failures = 0
            return True
        except:
            consecutive_failures += 1
            return False
    except Exception as e:
        consecutive_failures += 1
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            await check_spam_block()
        return False


async def safe_forward_message(user_entity, message):
    global spam_blocked, last_successful_send, consecutive_failures

    if spam_blocked:
        return False

    try:
        if isinstance(message, Message):
            await client.forward_messages(user_entity, message)
        else:
            await client.send_message(user_entity, message)

        last_successful_send = datetime.now()
        consecutive_failures = 0
        return True
    except FloodWaitError as e:
        print(f"\n⏳ Флуд {e.seconds}с")
        await asyncio.sleep(e.seconds)
        try:
            if isinstance(message, Message):
                await client.forward_messages(user_entity, message)
            else:
                await client.send_message(user_entity, message)
            last_successful_send = datetime.now()
            consecutive_failures = 0
            return True
        except:
            consecutive_failures += 1
            return False
    except Exception as e:
        consecutive_failures += 1
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            await check_spam_block()
        return False


async def get_admin_messages():
    default_messages = [
        "Доброго времени суток! Вы выиграли у нас @PoizonCountry в кoнкурсe 07.02 \n\n🥈- Egor Sobolev 🤩\n\nБесплaтнaя доставкa бeз комиcсии +25% cкидкa нa зaкaз",
        "Здравствуйтe! Вы выигрaли у нас @PoizonCountry в кoнкурсе 07.02 \n\n🥈- Egor Sobolev 🤩\n\nБесплатнaя доставкa бeз комиссии +25% скидка нa закaз",
        "Добрый день! Вы побeдили у нaс @PoizonCountry в кoнкурсe 07.02 \n\n🥈- Egor Sobolev 🤩\n\nБесплатнaя доставкa бeз комиссии +25% скидкa нa закaз"
    ]

    try:
        admin_chat = await client.get_entity(ADMIN_USERNAME)
        print(f"📨 Чат с админом: {ADMIN_USERNAME}")

        messages = await client.get_messages(admin_chat, limit=50)

        win_messages = []
        search_phrases = ['выиграли', 'выигрaли', 'побeдили', 'Egor Sobolev']

        for msg in messages:
            if msg.text and any(phrase in msg.text for phrase in search_phrases):
                win_messages.append(msg)
                print(f"  ✓ Найдено: {msg.text[:30]}...")
                if len(win_messages) >= 3:
                    break

        if len(win_messages) >= 3:
            return win_messages[:3]
        else:
            return default_messages

    except Exception as e:
        print(f"❌ Ошибка загрузки сообщений: {e}")
        return default_messages


async def main():
    global spam_blocked, stats

    stats['start_time'] = time.time()

    print("\n" + "=" * 60)
    print("🚀 ЗАПУСК СКРИПТА (РАНТАЙМ ФИЛЬТРАЦИЯ)")
    print("=" * 60)

    # Загружаем статус спама
    spam_blocked = load_spam_status()
    if spam_blocked:
        print("⚠️ Был спам-блок, проверяем...")

    # Авторизация
    try:
        await client.connect()

        if not await client.is_user_authorized():
            print("\n🔐 Требуется авторизация")
            await client.send_code_request(phone)
            code = input("📱 Код из Telegram: ")

            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input("🔑 Пароль 2FA: ")
                await client.sign_in(password=password)

            print("✅ Авторизация успешна!")

        print(f"✅ Аккаунт: {(await client.get_me()).username}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return

    # Проверка спама
    await check_spam_block()

    if spam_blocked:
        await wait_if_spam_blocked()

    # Получаем сообщения админа
    admin_messages = await get_admin_messages()

    # Получаем канал
    try:
        entity = await client.get_entity(TARGET_CHANNEL)
        print(f"\n📢 Канал: {entity.title}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return

    # Получаем участников (НО НЕ АНАЛИЗИРУЕМ ВСЕХ СРАЗУ!)
    print("📥 Загружаю список участников...")
    participants = await client.get_participants(entity)
    total_users = len([u for u in participants if not u.bot and u.username])
    print(f"👥 Всего участников с username: {total_users}")

    processed = load_processed_users()
    forward_counter = load_forward_counter()

    print(f"\n📊 Стартовая статистика:")
    print(f"  • Уже обработано: {len(processed)}")
    print(f"  • Счетчик пересылок: {forward_counter}")
    print(f"  • Лимит на сегодня: {MAX_DAILY_MESSAGES}")
    print("\n🔍 Начинаю поиск офлайн-пользователей...\n")

    # РАНТАЙМ ФИЛЬТРАЦИЯ - проверяем и сразу пишем
    for i, user in enumerate(participants):
        # Базовые проверки
        if user.bot or not user.username or (await client.get_me()).id == user.id:
            continue

        if str(user.id) in processed:
            continue

        # Проверяем статус
        stats['total_checked'] += 1

        if is_user_offline(user):
            # НАШЕЛ ОФЛАЙН - СРАЗУ ПИШЕМ!
            stats['offline_found'] += 1

            # Показываем статус
            print_status(stats['total_checked'], total_users, user, "found")

            # Проверяем лимит
            if stats['sent_count'] >= MAX_DAILY_MESSAGES:
                print(f"\n\n✅ Достигнут дневной лимит ({MAX_DAILY_MESSAGES})")
                break

            # Отправляем сообщения
            try:
                # Первое сообщение
                msg1 = get_random_message(FIRST_MESSAGES_RU, FIRST_MESSAGES_EN)
                if await safe_send_message(user.username, msg1):
                    await asyncio.sleep(random.randint(30, 60))

                    # Второе сообщение
                    msg2 = get_random_message(SECOND_MESSAGES_RU, SECOND_MESSAGES_EN)
                    if await safe_send_message(user.username, msg2):
                        await asyncio.sleep(random.randint(20, 40))

                        # Пересылка поздравления
                        msg_index = forward_counter % 3
                        if await safe_forward_message(user.username, admin_messages[msg_index]):
                            forward_counter += 1
                            save_forward_counter(forward_counter)

                            # Сохраняем успех
                            stats['sent_count'] += 1
                            save_processed_user(str(user.id))
                            processed.add(str(user.id))

                            # Обновляем статус
                            print_status(stats['total_checked'], total_users)

                            # Ждем перед следующим (кроме последнего)
                            if stats['sent_count'] < MAX_DAILY_MESSAGES:
                                wait_time = DELAY_BETWEEN_MESSAGES + random.randint(10, 60)
                                await asyncio.sleep(wait_time)

            except Exception as e:
                print(f"\n❌ Ошибка отправки @{user.username}: {e}")
                continue
        else:
            # Онлайн - пропускаем
            stats['online_skipped'] += 1
            if i % 5 == 0:  # Обновляем статус каждые 5 пропусков
                print_status(stats['total_checked'], total_users, user, "skip")

    # Финальная статистика
    elapsed = time.time() - stats['start_time']
    print("\n\n" + "=" * 60)
    print("✅ РАБОТА ЗАВЕРШЕНА")
    print("=" * 60)
    print(f"📊 Статистика:")
    print(f"  • Проверено пользователей: {stats['total_checked']}")
    print(f"  • Найдено офлайн: {stats['offline_found']}")
    print(f"  • Онлайн (пропущено): {stats['online_skipped']}")
    print(f"  • Отправлено сообщений: {stats['sent_count']}")
    print(f"  • Время работы: {str(timedelta(seconds=int(elapsed)))}")
    print(f"  • Счетчик пересылок: {forward_counter}")
    print("=" * 60)

    save_stats()


if __name__ == '__main__':
    asyncio.run(main())