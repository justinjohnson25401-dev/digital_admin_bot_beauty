#!/usr/bin/env python3
"""
Установщик бота для салонов красоты
Поддерживает 3 формата: соло-мастер, мини-студия, салон красоты
"""

import os
import sys
import json
import subprocess
import re

# ==================== ВЕРСИЯ БОТА ====================
BOT_VERSION = "2.7.0"
BOT_BUILD_DATE = "2026-01-02 16:40"
# =====================================================

TEMPLATES = {
    "1": {
        "name": "Соло-мастер",
        "file": "templates/solo_master.json",
        "desc": "Частный мастер (1-2 человека), без выбора мастера"
    },
    "2": {
        "name": "Мини-студия",
        "file": "templates/mini_studio.json",
        "desc": "Студия на 3-5 мастеров с выбором специалиста"
    },
    "3": {
        "name": "Салон красоты",
        "file": "templates/beauty_salon.json",
        "desc": "Полноценный салон на 5-8 мастеров"
    }
}


def print_header():
    print("\n" + "=" * 55)
    print("  🎀 УСТАНОВЩИК БОТА ДЛЯ САЛОНА КРАСОТЫ")
    print(f"  📦 Версия: {BOT_VERSION} ({BOT_BUILD_DATE})")
    print("=" * 55 + "\n")


def print_step(num, text):
    print(f"\n📌 Шаг {num}: {text}")
    print("-" * 45)


def validate_token(token: str) -> bool:
    """Проверка формата Telegram Bot Token"""
    if len(token) < 20 or ":" not in token:
        return False
    return True


def get_input(prompt, default=None, validator=None):
    """Получить ввод пользователя с поддержкой значения по умолчанию"""
    while True:
        if default:
            result = input(f"{prompt} [{default}]: ").strip()
            result = result if result else default
        else:
            result = input(f"{prompt}: ").strip()

        if not result:
            print("❌ Это поле обязательное!")
            continue

        if validator and not validator(result):
            print("❌ Некорректный формат! Попробуйте ещё раз.")
            continue

        return result


def choose_template():
    """Выбор шаблона бизнеса"""
    print_step(1, "Выберите формат вашего бизнеса")

    for key, tmpl in TEMPLATES.items():
        print(f"\n  [{key}] {tmpl['name']}")
        print(f"      └─ {tmpl['desc']}")

    print()
    while True:
        choice = input("Ваш выбор (1/2/3): ").strip()
        if choice in TEMPLATES:
            return TEMPLATES[choice]
        print("❌ Введите 1, 2 или 3")


def load_template(template_file):
    """Загрузить шаблон конфигурации"""
    if not os.path.exists(template_file):
        print(f"❌ Файл шаблона не найден: {template_file}")
        sys.exit(1)

    with open(template_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('config', data)


def get_tokens():
    """Получить токены ботов"""
    print_step(2, "Введите токены Telegram ботов")

    print("\n💡 Получить токен можно у @BotFather в Telegram")
    print("   1. Откройте @BotFather → /newbot")
    print("   2. Введите имя и username бота")
    print("   3. Скопируйте полученный токен\n")

    bot_token = get_input(
        "BOT_TOKEN (основной бот)",
        validator=validate_token
    )

    admin_token = get_input(
        "ADMIN_BOT_TOKEN (админ-панель)",
        validator=validate_token
    )

    return bot_token, admin_token


def get_admin_id():
    """Получить Telegram ID администратора"""
    print_step(3, "Введите ваш Telegram ID")

    print("\n💡 Узнать свой ID можно у бота @userinfobot")
    print("   Просто напишите ему /start\n")

    while True:
        admin_id = get_input("Ваш Telegram ID")
        if admin_id.isdigit() and len(admin_id) >= 5:
            return int(admin_id)
        print("❌ ID должен быть числом (например: 123456789)")


def get_business_name(default_name):
    """Получить название бизнеса"""
    print_step(4, "Название вашего бизнеса")
    return get_input("Название", default_name)


def create_env_file(bot_token, admin_token):
    """Создать .env файл"""
    env_content = f"""# Токены ботов
BOT_TOKEN={bot_token}
ADMIN_BOT_TOKEN={admin_token}

# Настройки логирования
LOG_LEVEL=INFO
"""

    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)

    print("✅ Создан файл .env")


def create_config(config, business_name, admin_id, slug):
    """Создать конфигурационный файл"""
    config['business_name'] = business_name
    config['business_slug'] = slug
    config['admin_ids'] = [admin_id]

    os.makedirs('configs', exist_ok=True)
    config_path = 'configs/client_lite.json'

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✅ Создан конфиг: {config_path}")
    return slug


def install_dependencies():
    """Установить зависимости"""
    print_step(5, "Установка зависимостей")

    if not os.path.exists('requirements.txt'):
        print("⚠️ Файл requirements.txt не найден, пропускаем")
        return

    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'],
            check=True,
            capture_output=True
        )
        print("✅ Зависимости установлены")
    except subprocess.CalledProcessError:
        print("⚠️ Ошибка установки зависимостей. Запустите вручную:")
        print("   pip install -r requirements.txt")


def init_database(slug):
    """Инициализировать базу данных"""
    print_step(6, "Инициализация базы данных")

    try:
        from utils.db_manager import DBManager
        db = DBManager(slug)
        db.init_db()
        db.close()
        print(f"✅ База данных создана: db_{slug}.sqlite")
    except Exception as e:
        print(f"⚠️ Ошибка инициализации БД: {e}")
        print("   База будет создана при первом запуске бота")


def print_success():
    """Вывести инструкции по запуску"""
    print("\n" + "=" * 55)
    print("  ✅ УСТАНОВКА ЗАВЕРШЕНА!")
    print("=" * 55)

    print("""
📋 Что дальше:

1. Запустите клиентского бота:
   python main.py

2. В отдельном терминале запустите админ-панель:
   python admin_bot/main.py

3. Откройте вашего бота в Telegram и нажмите /start

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Советы:
   • Настройки меняйте в configs/client_lite.json
   • Админ-панель доступна только владельцу (admin_ids)
   • Для фонового запуска: nohup python main.py &

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def main():
    print_header()

    # 1. Выбор шаблона
    template = choose_template()
    print(f"\n✅ Выбран: {template['name']}")

    # Загружаем конфиг из шаблона
    config = load_template(template['file'])
    default_name = config.get('business_name', 'Салон красоты')
    default_slug = config.get('business_slug', 'beauty_salon')

    # 2. Получаем токены
    bot_token, admin_token = get_tokens()

    # 3. Получаем ID администратора
    admin_id = get_admin_id()

    # 4. Получаем название бизнеса
    business_name = get_business_name(default_name)

    slug = default_slug

    print("\n" + "=" * 55)
    print("  📝 СОЗДАНИЕ КОНФИГУРАЦИИ")
    print("=" * 55)

    # 5. Создаём .env
    create_env_file(bot_token, admin_token)

    # 6. Создаём конфиг
    create_config(config, business_name, admin_id, slug)

    # 7. Устанавливаем зависимости
    install_dependencies()

    # 8. Инициализируем БД
    init_database(slug)

    # 9. Выводим инструкции
    print_success()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Установка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
