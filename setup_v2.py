#!/usr/bin/env python3
"""
BOT-BUSINESS V2.1 - Умный установщик с готовыми шаблонами
Настройка бота для ЛЮБОГО бизнеса за 3 минуты
"""

import os
import json
import sys
import subprocess
import re
import hashlib
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / 'templates'

def print_header():
    """Красивый заголовок"""
    print("\n" + "="*70)
    print("   🚀 BOT-BUSINESS V2.1 — УМНЫЙ УСТАНОВЩИК")
    print("="*70 + "\n")
    print("Настройте бота для ЛЮБОГО бизнеса за 3 минуты!")
    print("✅ 7 готовых шаблонов")
    print("✅ Автоматическая настройка")
    print("✅ Запуск в один клик\n")

def load_templates():
    """Загрузка всех шаблонов"""
    templates = []

    if not TEMPLATES_DIR.exists():
        print(f"⚠️ Папка templates/ не найдена!")
        return []

    for template_file in sorted(TEMPLATES_DIR.glob('*.json')):
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template = json.load(f)
                template['_file'] = template_file.name
                templates.append(template)
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {template_file.name}: {e}")

    return templates

def show_templates_menu(templates):
    """Показать меню выбора шаблона"""
    print("="*70)
    print("   ВЫБЕРИТЕ ВАШ ТИП БИЗНЕСА")
    print("="*70 + "\n")

    for idx, template in enumerate(templates, 1):
        name = template.get('template_name', 'Без названия')
        desc = template.get('description', '')
        print(f"  [{idx}] {name}")
        if desc:
            print(f"      {desc}\n")

    print(f"  [0] Выход\n")

def select_template(templates):
    """Интерактивный выбор шаблона"""
    while True:
        try:
            choice = input("Ваш выбор (введите номер): ").strip()

            if choice == '0':
                print("\n❌ Установка отменена")
                sys.exit(0)

            idx = int(choice) - 1
            if 0 <= idx < len(templates):
                return templates[idx]
            else:
                print(f"❌ Некорректный номер. Введите число от 1 до {len(templates)}")
        except ValueError:
            print("❌ Введите число!")
        except KeyboardInterrupt:
            print("\n\n❌ Установка отменена")
            sys.exit(0)

def validate_token(token: str) -> bool:
    """Проверка формата Telegram Bot Token"""
    pattern = r'^\d{8,10}:[A-Za-z0-9_-]{35}$'
    return bool(re.match(pattern, token))

def validate_telegram_id(user_id: str) -> bool:
    """Проверка Telegram ID"""
    return user_id.isdigit() and len(user_id) >= 5

def validate_slug(slug: str) -> bool:
    """Проверка slug (только латиница, цифры, подчеркивание)"""
    pattern = r'^[a-z0-9_]+$'
    return bool(re.match(pattern, slug))

def input_with_validation(prompt: str, validator=None, required=True, default=None):
    """Ввод с валидацией"""
    while True:
        value = input(prompt).strip()

        if not value and default:
            return default

        if not value and not required:
            return None

        if not value and required:
            print("❌ Это поле обязательное!")
            continue

        if validator:
            if validator(value):
                return value
            else:
                print("❌ Некорректный формат! Попробуйте еще раз.")
        else:
            return value

def create_env_file(bot_token: str, admin_bot_token: str = None):
    """Создание .env файла"""
    content = f"# Токены ботов\nBOT_TOKEN={bot_token}\n"

    if admin_bot_token:
        content += f"ADMIN_BOT_TOKEN={admin_bot_token}\n"

    with open('.env', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Файл .env создан")

def flatten_services(template_config):
    """Преобразование категорий в плоский список services"""
    if 'categories' in template_config:
        # Если есть категории, объединяем все services в один список
        all_services = []
        for category in template_config.get('categories', []):
            for service in category.get('services', []):
                # Добавляем метку категории к каждому сервису
                service['category_id'] = category['id']
                service['category_name'] = category['name']
                all_services.append(service)
        template_config['services'] = all_services
        # Удаляем categories, так как теперь всё в services
        del template_config['categories']

    return template_config

def create_config_file(template, user_data: dict):
    """Создание конфигурации на основе шаблона"""
    os.makedirs('configs', exist_ok=True)

    # Берём базовую конфигурацию из шаблона
    config = template['config'].copy()

    # Переопределяем пользовательские данные
    config['business_name'] = user_data.get('business_name') or config.get('business_name', 'Мой бизнес')
    config['business_slug'] = user_data.get('slug') or config.get('business_slug', 'my_business')
    config['admin_ids'] = [int(user_data['admin_id'])]

    # Добавляем тип бизнеса из шаблона
    config['business_type'] = template.get('business_type', 'time_slots')

    # Преобразуем категории в services если нужно
    config = flatten_services(config)

    # Обязательные поля
    if 'bot_token' not in config:
        config['bot_token'] = 'FROM_ENV'

    if 'config_version' not in config:
        config['config_version'] = 0

    # PIN для админа
    if user_data.get('admin_pin_hash'):
        config['admin_pin_hash'] = user_data['admin_pin_hash']

    # Тестовый пользователь
    if user_data.get('test_user_id'):
        config['admin_ids'].append(int(user_data['test_user_id']))

    # Сохраняем
    config_path = 'configs/client_lite.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✅ Конфигурация создана: {config_path}")
    return config_path

def install_dependencies():
    """Установка зависимостей"""
    print("\n📦 Установка зависимостей...")

    if not os.path.exists('requirements.txt'):
        print("⚠️  requirements.txt не найден, создаём...")
        with open('requirements.txt', 'w') as f:
            f.write("aiogram==3.15.0\n")
            f.write("python-dotenv==1.0.0\n")
            f.write("apscheduler==3.10.4\n")

    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                      check=True, capture_output=True)
        print("✅ Зависимости установлены")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False

def init_database(config_path: str):
    """Инициализация базы данных"""
    print("\n💾 Инициализация базы данных...")

    try:
        from utils.db_manager import DBManager

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        db_manager = DBManager(config['business_slug'])
        db_manager.init_db()
        db_manager.close()

        print(f"✅ База данных создана: db_{config['business_slug']}.sqlite")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

def main():
    """Главная функция установщика"""
    print_header()

    # Загружаем шаблоны
    templates = load_templates()

    if not templates:
        print("❌ Шаблоны не найдены в папке templates/")
        sys.exit(1)

    # Показываем меню и выбираем шаблон
    show_templates_menu(templates)
    selected_template = select_template(templates)

    print("\n" + "="*70)
    print(f"   ✅ Выбран шаблон: {selected_template['template_name']}")
    print("="*70 + "\n")

    # Минимальный набор вопросов
    print("Ответьте на несколько вопросов для настройки бота:\n")

    # 1. Bot Token
    print("[1/5] Введите TOKEN основного бота (от @BotFather):")
    print("      Если нет, откройте Telegram → @BotFather → /newbot")
    bot_token = input_with_validation(
        "> ",
        validator=validate_token,
        required=True
    )

    # 2. Admin ID
    print("\n[2/5] Введите ваш Telegram ID (админ/владелец):")
    print("      Узнать ID: напишите боту @userinfobot")
    admin_id = input_with_validation(
        "> ",
        validator=validate_telegram_id,
        required=True
    )

    # 3. Business Name (необязательно, есть в шаблоне)
    default_name = selected_template['config'].get('business_name', 'Мой бизнес')
    print(f"\n[3/5] Название вашего бизнеса (по умолчанию: {default_name}):")
    print("      Или нажмите Enter чтобы использовать название из шаблона")
    business_name = input_with_validation(
        "> ",
        required=False,
        default=default_name
    )

    # 4. Slug (необязательно, есть в шаблоне)
    default_slug = selected_template['config'].get('business_slug', 'my_business')
    print(f"\n[4/5] Slug для базы данных (по умолчанию: {default_slug}):")
    print("      Только строчные буквы, цифры и подчеркивание")
    print("      Или нажмите Enter чтобы использовать slug из шаблона")
    slug = input_with_validation(
        "> ",
        validator=lambda x: validate_slug(x) if x else True,
        required=False,
        default=default_slug
    )

    # 5. Admin Bot (необязательно)
    print("\n[5/5] Создать отдельного бота для админ-панели? (y/n):")
    print("      Рекомендуется для удобства управления")
    create_admin_bot = input("> ").strip().lower() == 'y'

    admin_bot_token = None
    admin_pin_hash = None

    if create_admin_bot:
        print("\n      Введите TOKEN админ-бота (от @BotFather):")
        admin_bot_token = input_with_validation(
            "> ",
            validator=validate_token,
            required=True
        )

        print("\n      Установить PIN для админ-панели? (y/n):")
        enable_pin = input("> ").strip().lower() == 'y'
        if enable_pin:
            while True:
                pin = input("Введите PIN (минимум 4 цифры): ").strip()
                if not (pin.isdigit() and len(pin) >= 4):
                    print("❌ PIN должен быть минимум из 4 цифр")
                    continue
                admin_pin_hash = hashlib.sha256(pin.encode('utf-8')).hexdigest()
                break

    # Сохраняем данные
    user_data = {
        'bot_token': bot_token,
        'admin_id': admin_id,
        'business_name': business_name,
        'slug': slug,
        'admin_bot_token': admin_bot_token,
        'admin_pin_hash': admin_pin_hash,
    }

    print("\n" + "="*70)
    print("   📝 СОЗДАНИЕ КОНФИГУРАЦИИ")
    print("="*70 + "\n")

    # Создаём файлы
    create_env_file(bot_token, admin_bot_token)
    config_path = create_config_file(selected_template, user_data)

    # Устанавливаем зависимости
    if not install_dependencies():
        print("\n⚠️  Продолжаем без установки зависимостей...")

    # Инициализируем БД
    if not init_database(config_path):
        print("\n⚠️  База данных не инициализирована. Запустите вручную:")
        print(f"   python main.py --config {config_path}")

    # Финальное сообщение
    print("\n" + "="*70)
    print("   ✅ УСТАНОВКА ЗАВЕРШЕНА!")
    print("="*70 + "\n")

    print(f"🎯 Выбранный шаблон: {selected_template['template_name']}")
    print(f"📊 Тип бизнеса: {selected_template.get('business_type', 'custom')}\n")

    print("🚀 Запустите бота командой:")
    print(f"   python main.py --config {config_path}\n")

    if create_admin_bot:
        print("🔧 Для запуска админ-бота:")
        print(f"   python admin_bot/main.py --config {config_path}\n")

    print("⚙️  Настройте услуги и FAQ в файле:")
    print(f"   {config_path}\n")

    print("📚 Доступные шаблоны можно посмотреть в папке templates/")
    print("="*70 + "\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Установка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
