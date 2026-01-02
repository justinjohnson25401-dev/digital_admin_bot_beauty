# 🔗 Настройка Webhook для Telegram-бота

## 📖 Что такое Webhook (простыми словами)

**Сейчас ваш бот работает в режиме Polling:**
- Бот каждые 2-3 секунды спрашивает у Telegram: "Есть новые сообщения?"
- Telegram отвечает: "Да, вот они" или "Нет, пока нет"
- Это как постоянно проверять почтовый ящик - тратится время и ресурсы

**Webhook - это как почтальон:**
- Вы говорите Telegram: "Когда будет сообщение, доставь его сюда"
- Telegram сам присылает сообщения на ваш сервер
- Не нужно постоянно опрашивать - экономия ресурсов!

---

## ✅ Когда нужен Webhook

**Используйте Webhook если:**
- ✅ Бот работает на сервере 24/7 (не локальный компьютер)
- ✅ Много пользователей (>100 активных в день)
- ✅ Хотите экономить ресурсы сервера
- ✅ Есть доменное имя (например, mybusiness.ru)

**Оставьте Polling если:**
- ❌ Бот на локальном компьютере (дома/офис)
- ❌ Мало пользователей (<50 в день)
- ❌ Нет доменного имени
- ❌ Не хотите разбираться с HTTPS

---

## 🔐 Обязательные требования

Для работы Webhook **обязательно** нужны:

1. **Доменное имя** (например: `bot.mybusiness.ru`)
   - Нельзя использовать просто IP-адрес
   - Можно купить домен за 200-500р/год на reg.ru, nic.ru

2. **SSL-сертификат (HTTPS)**
   - Telegram принимает только HTTPS-соединения
   - Бесплатный сертификат: Let's Encrypt (рекомендуем)
   - Платный: от 1000р/год

3. **Открытый порт** (обычно 443 или 8443)
   - Должен быть доступен из интернета
   - Настраивается в firewall вашего сервера

---

## 📋 Шаг 1: Установка веб-сервера (nginx)

### Ubuntu/Debian:

```bash
# Обновляем систему
sudo apt update

# Устанавливаем nginx
sudo apt install nginx -y

# Проверяем что nginx запущен
sudo systemctl status nginx
```

### CentOS/RHEL:

```bash
sudo yum install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## 🔒 Шаг 2: Получение SSL-сертификата (Let's Encrypt)

```bash
# Устанавливаем certbot
sudo apt install certbot python3-certbot-nginx -y

# Получаем сертификат (замените на ваш домен!)
sudo certbot --nginx -d bot.yourdomain.com

# Следуйте инструкциям на экране:
# 1. Введите email для уведомлений
# 2. Согласитесь с условиями
# 3. Выберите автоматическое перенаправление HTTP -> HTTPS
```

**Сертификат установлен!** Он автоматически обновляется каждые 3 месяца.

---

## ⚙️ Шаг 3: Настройка nginx для бота

Создайте конфигурацию для вашего бота:

```bash
sudo nano /etc/nginx/sites-available/telegram-bot
```

Вставьте следующую конфигурацию (замените `bot.yourdomain.com` на ваш домен):

```nginx
# Конфигурация для клиентского бота
server {
    listen 443 ssl http2;
    server_name bot.yourdomain.com;

    # SSL-сертификаты (certbot настроил автоматически)
    ssl_certificate /etc/letsencrypt/live/bot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.yourdomain.com/privkey.pem;

    # Webhook для клиентского бота
    location /webhook/client {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Webhook для админ-бота
    location /webhook/admin {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Редирект с HTTP на HTTPS
server {
    listen 80;
    server_name bot.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

Активируйте конфигурацию:

```bash
# Создаем символическую ссылку
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/

# Проверяем конфигурацию
sudo nginx -t

# Перезапускаем nginx
sudo systemctl reload nginx
```

---

## 🤖 Шаг 4: Изменение кода бота для Webhook

Создайте файл `main_webhook.py` в корне проекта:

```python
#!/usr/bin/env python3
"""
Telegram-бот с Webhook вместо Polling
"""
import asyncio
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp

# Импорты из вашего проекта
from handlers import registration_handlers, client_handlers
from utils.db_manager import DatabaseManager
from utils.config import BotConfig

# Настройки Webhook
WEBHOOK_HOST = "https://bot.yourdomain.com"  # Замените на ваш домен!
WEBHOOK_PATH_CLIENT = "/webhook/client"
WEBHOOK_PATH_ADMIN = "/webhook/admin"
WEBHOOK_URL_CLIENT = f"{WEBHOOK_HOST}{WEBHOOK_PATH_CLIENT}"
WEBHOOK_URL_ADMIN = f"{WEBHOOK_HOST}{WEBHOOK_PATH_ADMIN}"

# Порты для локального сервера
WEBAPP_HOST = "127.0.0.1"
WEBAPP_PORT_CLIENT = 8080
WEBAPP_PORT_ADMIN = 8081

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup_client(bot: Bot, config: BotConfig):
    """Действия при запуске клиентского бота"""
    # Устанавливаем webhook
    await bot.set_webhook(
        url=WEBHOOK_URL_CLIENT,
        drop_pending_updates=True
    )
    logger.info(f"Webhook установлен: {WEBHOOK_URL_CLIENT}")


async def on_startup_admin(bot: Bot):
    """Действия при запуске админ-бота"""
    await bot.set_webhook(
        url=WEBHOOK_URL_ADMIN,
        drop_pending_updates=True
    )
    logger.info(f"Webhook установлен: {WEBHOOK_URL_ADMIN}")


async def on_shutdown(bot: Bot):
    """Действия при остановке"""
    await bot.delete_webhook()
    logger.info("Webhook удален")


async def main():
    """Главная функция запуска"""
    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()

    client_bot_token = os.getenv("CLIENT_BOT_TOKEN")
    admin_bot_token = os.getenv("ADMIN_BOT_TOKEN")

    if not client_bot_token or not admin_bot_token:
        logger.error("Не заданы токены в .env файле!")
        return

    # Создаем HTTP-сессию с таймаутом
    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    session = AiohttpSession(timeout=timeout)

    # Создаем ботов
    client_bot = Bot(token=client_bot_token, session=session)
    admin_bot = Bot(token=admin_bot_token, session=session)

    # Создаем диспетчеры с хранилищем FSM
    storage = MemoryStorage()
    client_dp = Dispatcher(storage=storage)
    admin_dp = Dispatcher(storage=storage)

    # Загружаем конфигурацию и БД
    config = BotConfig("configs/client_lite.json")
    db_manager = DatabaseManager("data/bot_data.sqlite")

    # Регистрируем обработчики (ваши handlers)
    # client_dp.include_router(registration_handlers.router)
    # client_dp.include_router(client_handlers.router)
    # ... (добавьте все ваши роутеры)

    # Запускаем webhook для клиентского бота
    client_app = web.Application()
    client_handler = SimpleRequestHandler(dispatcher=client_dp, bot=client_bot)
    client_handler.register(client_app, path=WEBHOOK_PATH_CLIENT)
    setup_application(client_app, client_dp, bot=client_bot)

    # Запускаем webhook для админ-бота
    admin_app = web.Application()
    admin_handler = SimpleRequestHandler(dispatcher=admin_dp, bot=admin_bot)
    admin_handler.register(admin_app, path=WEBHOOK_PATH_ADMIN)
    setup_application(admin_app, admin_dp, bot=admin_bot)

    # Устанавливаем webhooks
    await on_startup_client(client_bot, config)
    await on_startup_admin(admin_bot)

    # Создаем веб-серверы
    client_runner = web.AppRunner(client_app)
    admin_runner = web.AppRunner(admin_app)
    await client_runner.setup()
    await admin_runner.setup()

    client_site = web.TCPSite(client_runner, WEBAPP_HOST, WEBAPP_PORT_CLIENT)
    admin_site = web.TCPSite(admin_runner, WEBAPP_HOST, WEBAPP_PORT_ADMIN)

    await client_site.start()
    await admin_site.start()

    logger.info(f"Клиентский бот: http://{WEBAPP_HOST}:{WEBAPP_PORT_CLIENT}{WEBHOOK_PATH_CLIENT}")
    logger.info(f"Админ-бот: http://{WEBAPP_HOST}:{WEBAPP_PORT_ADMIN}{WEBHOOK_PATH_ADMIN}")
    logger.info("Боты запущены в режиме Webhook!")

    # Ждем завершения
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    finally:
        await on_shutdown(client_bot)
        await on_shutdown(admin_bot)
        await client_runner.cleanup()
        await admin_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
```

**Важно!** Замените `bot.yourdomain.com` на ваш реальный домен в коде выше!

---

## 🚀 Шаг 5: Запуск бота с Webhook

```bash
# Остановите старый бот (если запущен)
# Ctrl+C или найдите процесс и убейте его

# Запустите новый бот с webhook
python3 main_webhook.py

# Для запуска в фоне (рекомендуется)
nohup python3 main_webhook.py > webhook.log 2>&1 &
```

---

## ✅ Шаг 6: Проверка работы Webhook

### 1. Проверьте статус webhook:

```bash
# Для клиентского бота (замените TOKEN на ваш токен)
curl "https://api.telegram.org/botTOKEN/getWebhookInfo"
```

Ответ должен содержать:
```json
{
  "ok": true,
  "result": {
    "url": "https://bot.yourdomain.com/webhook/client",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

### 2. Проверьте логи nginx:

```bash
sudo tail -f /var/log/nginx/access.log
```

Когда вы отправите сообщение боту, должны появиться записи вида:
```
POST /webhook/client HTTP/1.1
```

### 3. Проверьте логи бота:

```bash
tail -f webhook.log
```

---

## 🔧 Настройка systemd для автозапуска

Создайте службу для автозапуска при перезагрузке сервера:

```bash
sudo nano /etc/systemd/system/telegram-bot-webhook.service
```

Вставьте:

```ini
[Unit]
Description=Telegram Bot Webhook
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/digital_admin_bot
ExecStart=/usr/bin/python3 /path/to/digital_admin_bot/main_webhook.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Замените:
- `your_username` на имя пользователя
- `/path/to/digital_admin_bot` на реальный путь

Активируйте службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot-webhook
sudo systemctl start telegram-bot-webhook

# Проверьте статус
sudo systemctl status telegram-bot-webhook
```

---

## 🐛 Решение проблем

### Проблема: Webhook не работает

**Проверьте:**
1. Доменное имя указывает на IP вашего сервера
   ```bash
   nslookup bot.yourdomain.com
   ```

2. Порты открыты в firewall
   ```bash
   sudo ufw status
   sudo ufw allow 443/tcp
   ```

3. nginx работает
   ```bash
   sudo systemctl status nginx
   ```

4. SSL-сертификат валиден
   ```bash
   sudo certbot certificates
   ```

### Проблема: 502 Bad Gateway

Это означает, что nginx не может соединиться с ботом.

**Решение:**
1. Убедитесь что бот запущен
2. Проверьте порты в `main_webhook.py` (8080, 8081)
3. Проверьте логи: `tail -f webhook.log`

### Проблема: Certificate verification failed

Возможно проблема с SSL-сертификатом.

**Решение:**
```bash
# Обновите сертификат
sudo certbot renew

# Перезапустите nginx
sudo systemctl reload nginx
```

---

## 🔄 Возврат к Polling

Если webhook не подходит, можно вернуться к polling:

```bash
# Удалите webhook
curl "https://api.telegram.org/botYOUR_TOKEN/deleteWebhook"

# Запустите старый вариант
python3 main.py --config configs/client_lite.json
```

---

## 📊 Сравнение Polling vs Webhook

| Характеристика | Polling | Webhook |
|----------------|---------|---------|
| **Сложность настройки** | Просто (5 минут) | Сложнее (30-60 минут) |
| **Требования** | Только токен бота | Домен + SSL + сервер |
| **Нагрузка на сервер** | Выше (постоянные запросы) | Ниже (запросы по требованию) |
| **Скорость отклика** | 2-3 секунды задержка | Мгновенно |
| **Локальная разработка** | ✅ Работает | ❌ Не работает |
| **Для продакшена** | ❌ Не рекомендуется | ✅ Рекомендуется |
| **Лимиты Telegram** | 30 запросов/сек | Без ограничений |

---

## ✅ Готово!

Ваш бот теперь работает на webhook! Преимущества:
- ⚡ Быстрый отклик на сообщения
- 💰 Экономия ресурсов сервера
- 🚀 Готовность к большому потоку пользователей

**Документация Telegram Webhook:** https://core.telegram.org/bots/webhooks

---

## 📞 Нужна помощь?

- Telegram Bot API: https://core.telegram.org/bots/api
- Let's Encrypt: https://letsencrypt.org/
- nginx документация: https://nginx.org/ru/docs/
