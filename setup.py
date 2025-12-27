#!/usr/bin/env python3
"""
BOT-BUSINESS V2.0 - Интерактивный установщик
Настройка бота для вашего бизнеса за 5 минут
"""

import os
import json
import sys
import subprocess
import re
import hashlib

def print_header():
    """Красивый заголовок"""
    print("\n" + "="*60)
    print("   BOT-BUSINESS V2.0 — УСТАНОВЩИК")
    print("="*60 + "\n")
    print("Добро пожаловать! Сейчас мы настроим бота для вашего бизнеса.\n")

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
        
        # Если пустой и есть default
        if not value and default:
            return default
        
        # Если пустой и не обязательный
        if not value and not required:
            return None
        
        # Если пустой и обязательный
        if not value and required:
            print("❌ Это поле обязательное!")
            continue
        
        # Валидация
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

def create_config_file(data: dict):
    """Создание configs/client_lite.json"""
    os.makedirs('configs', exist_ok=True)
    
    config = {
        "config_version": 0,
        "bot_token": "FROM_ENV",
        "business_slug": data['slug'],
        "business_name": data['business_name'],
        "admin_ids": [int(data['admin_id'])],
        
        "services": [
            {"id": "service1", "name": "Стрижка", "price": 1200},
            {"id": "service2", "name": "Стрижка + борода", "price": 1800},
            {"id": "service3", "name": "Укладка", "price": 800}
        ],
        
        "booking": {
            "work_start": 10,
            "work_end": 20,
            "slot_duration": 60
        },
        
        "features": {
            "enable_slot_booking": True,
            "enable_admin_notify": True,
            "require_phone": True,
            "ask_comment": True
        },
        
        "messages": {
            "welcome": f"Добро пожаловать в {data['business_name']}! 👋\n\nВыберите действие:",
            "success": "✅ Заявка #{id} принята! Мы свяжемся с вами в ближайшее время.",
            "booking_cancelled": "✅ Запись отменена",
            "error_phone": "❌ Некорректный формат номера. Введите в формате +79991234567",
            "error_generic": "❌ Произошла ошибка. Попробуйте позже.",
            "slot_taken": "❌ Это время уже занято"
        },
        
        "faq": [
            {"btn": "💰 Цены", "answer": "Наши цены:\n• Стрижка — 1200₽\n• Стрижка + борода — 1800₽\n• Укладка — 800₽"},
            {"btn": "📍 Адрес", "answer": "📍 Наш адрес: уточните в настройках"},
            {"btn": "🕐 Часы работы", "answer": "🕐 Мы работаем:\nПн-Пт: 10:00-20:00\nСб-Вс: 12:00-18:00"}
        ]
    }

    pin_hash = data.get('admin_pin_hash')
    if isinstance(pin_hash, str) and pin_hash.strip():
        config['admin_pin_hash'] = pin_hash
    
    # Добавляем тестовый ID если указан
    if data.get('test_user_id'):
        config['admin_ids'].append(int(data['test_user_id']))
    
    with open('configs/client_lite.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("✅ Конфигурация создана: configs/client_lite.json")

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
        # Импортируем db_manager
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
    
    # Шаг 1: BOT TOKEN
    print("[1/6] Введите TOKEN основного бота (от @BotFather):")
    print("      Формат: 1234567890:AAH3kJ...")
    bot_token = input_with_validation(
        "> ",
        validator=validate_token,
        required=True
    )
    
    # Шаг 2: Admin Telegram ID
    print("\n[2/6] Введите ваш Telegram ID (админ/владелец):")
    print("      Узнать ID можно через бота @userinfobot")
    admin_id = input_with_validation(
        "> ",
        validator=validate_telegram_id,
        required=True
    )
    
    # Шаг 3: Business Name
    print("\n[3/6] Название бизнеса (например, 'Барбершоп Стиль'):")
    business_name = input_with_validation(
        "> ",
        required=True
    )
    
    # Шаг 4: Slug
    print("\n[4/6] Уникальный slug (латиницей, например 'barbershop_style'):")
    print("      Только строчные буквы, цифры и подчеркивание")
    slug = input_with_validation(
        "> ",
        validator=validate_slug,
        required=True
    )
    
    # Шаг 5: Test User (опционально)
    print("\n[5/6] (Опционально) Telegram ID тестировщика:")
    print("      Нажмите Enter чтобы пропустить")
    test_user_id = input_with_validation(
        "> ",
        validator=lambda x: validate_telegram_id(x) if x else True,
        required=False
    )
    
    # Шаг 6: Admin Bot
    print("\n[6/6] Создать отдельного бота для админ-панели? (y/n):")
    create_admin_bot = input("> ").strip().lower() == 'y'
    
    admin_bot_token = None
    if create_admin_bot:
        print("\n      Введите TOKEN админ-бота:")
        admin_bot_token = input_with_validation(
            "> ",
            validator=validate_token,
            required=True
        )

    admin_pin_hash = None
    if create_admin_bot:
        print("\n[Дополнительно] Установить PIN для админ-панели? (y/n):")
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
    data = {
        'bot_token': bot_token,
        'admin_id': admin_id,
        'business_name': business_name,
        'slug': slug,
        'test_user_id': test_user_id,
        'admin_bot_token': admin_bot_token,
        'admin_pin_hash': admin_pin_hash,
    }
    
    print("\n" + "="*60)
    print("   СОЗДАНИЕ КОНФИГУРАЦИИ")
    print("="*60 + "\n")
    
    # Создаём файлы
    create_env_file(bot_token, admin_bot_token)
    create_config_file(data)
    
    # Устанавливаем зависимости
    if not install_dependencies():
        print("\n⚠️  Продолжаем без установки зависимостей...")
    
    # Инициализируем БД
    if not init_database('configs/client_lite.json'):
        print("\n⚠️  База данных не инициализирована. Запустите вручную:")
        print(f"   python main.py --config configs/client_lite.json")
    
    # Финальное сообщение
    print("\n" + "="*60)
    print("   ✅ УСТАНОВКА ЗАВЕРШЕНА!")
    print("="*60 + "\n")
    print("Запустите бота командой:")
    print(f"  python main.py --config configs/client_lite.json\n")
    
    if create_admin_bot:
        print("Для запуска админ-бота:")
        print("  python admin_bot/main.py --config configs/client_lite.json\n")
    
    print("Настройте услуги и FAQ в файле:")
    print("  configs/client_lite.json\n")
    print("="*60 + "\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Установка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        sys.exit(1)
