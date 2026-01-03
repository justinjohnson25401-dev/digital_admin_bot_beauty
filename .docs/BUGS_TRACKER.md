# 🐞 BUGS TRACKER

Этот файл отслеживает ошибки, найденные в проекте.

---

## 🎯 К ВЫПОЛНЕНИЮ

*   ⚠️ 263 стилистических замечания flake8 (пробелы, отступы, E302)
*   ⚠️ 6 использований bare except (E722)
*   ⚠️ 8 f-string без переменных (F541)

---

## ✅ ГОТОВО (2026-01-03, Claude Opus 4.5)

- [✅] **ModuleNotFoundError:** `utils.config_manager` не существует → заменено на `utils.config_editor`
- [✅] **AttributeError:** `staff_editor.router` → исправлено на `staff_router` из `admin_handlers.staff`
- [✅] **ImportError:** `DBManager` → заменено на `DatabaseManager` в setup.py
- [✅] **ImportError:** `is_date_closed_for_master` импортировался из `handlers.booking` → `handlers.booking.utils`
- [✅] **NameError:** `InlineKeyboardMarkup`, `InlineKeyboardButton` не импортированы в `admin_handlers/staff/schedule.py`
- [✅] **NameError:** `datetime` не импортирован в `admin_handlers/staff/keyboards.py`
- [✅] **TypeError:** `setup_logger()` вызывался с 2 аргументами вместо 0 в `admin_bot/main.py`
- [✅] **AttributeError:** Отсутствовали классы `DialogCalendar`, `DialogCalendarCallback` → созданы в `utils/calendar.py`
- [✅] **AttributeError:** Отсутствовали FSM состояния `add_closed_date_cal`, `add_closed_date_reason` → добавлены
- [✅] **AttributeError:** `router` не экспортировался из `handlers/booking` и `handlers/mybookings` → добавлены alias

---

## ✅ ГОТОВО (Предыдущие сессии)

- [✅] **ERROR #1, #5:** `AttributeError: 'Bot' object has no attribute '__name__'` в `admin_bot/main.py` и `main.py`.
- [✅] **ERROR #2, #6:** `TypeError: Dispatcher.__init__() missing 1 required positional argument: 'storage'` в `admin_bot/main.py` и `main.py`.
- [✅] **ERROR #3, #7:** `db_manager` не передавался в функции уведомлений, что вызывало ошибку при получении истории клиента.
- [✅] **ERROR #4:** Неправильный вызов `get_user_bookings` напрямую из `db_manager` вместо `db_manager.bookings` в `utils/notify.py`.
- [✅] **ERROR #8:** `AttributeError: 'StaffQueries' object has no attribute 'get_order_by_id'`, так как `StaffQueries` не наследовал `BookingQueries`.
- [✅] **РЕФАКТОРИНГ:** Модульная структура базы данных. `utils/db.py` был преобразован в пакет `utils/db/` с классом `DatabaseManager` для централизованного управления запросами.
