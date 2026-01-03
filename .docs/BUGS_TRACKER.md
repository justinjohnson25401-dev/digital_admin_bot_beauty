# BUGS_TRACKER.md — Трекер Багов и Проблем

> Последнее обновление: **2026-01-03**
> Аудит: **Claude Opus 4.5**

---

## КРИТИЧЕСКИЕ (P1) — Бот не запустится

| ID | Описание | Файл | Статус | Дата |
|:---|:---------|:-----|:-------|:-----|
| P1-1 | **Отсутствует модуль start:** `handlers/booking/__init__.py` импортирует несуществующий `start` модуль | `handlers/booking/__init__.py:7` | 🔴 Open | 2026-01-03 |
| P1-2 | **Неверный экспорт:** Импортируется `all_booking_routers`, но экспортируется `booking_router` | `handlers/__init__.py:10` | 🔴 Open | 2026-01-03 |
| P1-3 | **Неверный импорт keyboards:** Используется `..keyboards` вместо `.keyboards` | `handlers/booking/master.py:11` | 🔴 Open | 2026-01-03 |
| P1-4 | **Неверный импорт utils:** Используется `..utils` вместо `.utils` | `handlers/booking/master.py:12` | 🔴 Open | 2026-01-03 |
| P1-5 | **Неверный импорт keyboards:** Используется `..keyboards` вместо `.keyboards` | `handlers/booking/date.py:12` | 🔴 Open | 2026-01-03 |
| P1-6 | **Неверный импорт keyboards:** Используется `..keyboards` вместо `.keyboards` | `handlers/booking/time.py:12` | 🔴 Open | 2026-01-03 |

---

## ВЫСОКИЕ (P2) — Функциональность не работает

| ID | Описание | Файл | Статус | Дата |
|:---|:---------|:-----|:-------|:-----|
| P2-1 | **DatabaseManager — заглушка:** Класс содержит только stub-методы, реальная логика не подключена | `utils/db/__init__.py` | 🟡 Open | 2026-01-03 |
| P2-2 | **Дублирование mybookings:** Есть `handlers/mybookings.py` и `handlers/mybookings/` одновременно | `handlers/` | 🟡 Open | 2026-01-03 |

---

## СРЕДНИЕ (P3) — Требуют внимания

| ID | Описание | Файл | Статус | Дата |
|:---|:---------|:-----|:-------|:-----|
| P3-1 | **Отсутствует импорт Message:** В `master.py` используется `Message` без импорта | `handlers/booking/master.py:24` | 🟡 Open | 2026-01-03 |

---

## ИСПРАВЛЕННЫЕ

| ID | Описание | Файл | Статус | Дата найдена | Дата исправления |
|:---|:---------|:-----|:-------|:-------------|:-----------------|
| 001 | **Race Condition в бронировании:** Два пользователя бронируют один слот → второй получает ошибку без обратной связи | `handlers/booking/confirmation.py` | ✅ Fixed | 2024-05-21 | 2024-05-21 |

---

## КАК ИСПРАВИТЬ КРИТИЧЕСКИЕ БАГИ

### P1-1: Отсутствует модуль start

**Вариант A:** Убрать `start` из импорта в `handlers/booking/__init__.py`
```python
# Было:
from . import start, master, date, time, contact, confirmation, save

# Стало:
from . import master, date, time, contact, confirmation, save
```

**Вариант B:** Создать файл `handlers/booking/start.py` с нужным роутером

---

### P1-2: Неверный экспорт

**Исправить в `handlers/booking/__init__.py`:**
```python
# Добавить алиас для совместимости:
all_booking_routers = booking_router
```

**Или исправить в `handlers/__init__.py`:**
```python
# Было:
from .booking import all_booking_routers

# Стало:
from .booking import booking_router as all_booking_routers
```

---

### P1-3 — P1-6: Неверные относительные импорты

**Исправить `..` на `.` в указанных файлах:**

```python
# handlers/booking/master.py
# Было:
from ..keyboards import get_masters_keyboard
from ..utils import get_masters_for_service, get_master_by_id

# Стало:
from .keyboards import get_masters_keyboard
from .utils import get_masters_for_service, get_master_by_id
```

```python
# handlers/booking/date.py
# Было:
from ..keyboards import get_calendar_keyboard

# Стало:
from .keyboards import get_calendar_keyboard
```

```python
# handlers/booking/time.py
# Было:
from ..keyboards import get_time_slots_keyboard

# Стало:
from .keyboards import get_time_slots_keyboard
```

---

## СТАТИСТИКА

| Приоритет | Всего | Open | Fixed |
|-----------|-------|------|-------|
| P1 (Critical) | 6 | 6 | 0 |
| P2 (High) | 2 | 2 | 0 |
| P3 (Medium) | 1 | 1 | 0 |
| **Итого** | **9** | **9** | **0** |
