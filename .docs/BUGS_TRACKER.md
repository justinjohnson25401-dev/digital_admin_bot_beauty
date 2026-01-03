
# Трекер багов

## Исправленные (Сессия 2026-01-03)

*   [x] `ModuleNotFoundError` в `states/booking.py`
*   [x] `ImportError` (неверный импорт `FSMContext`) в `states/booking.py`
*   [x] `NameError: name 'Router' is not defined` в `handlers/common.py`
*   [x] `ImportError` (неиспользуемый `get_main_keyboard`) в `handlers/booking/booking.py`
*   [x] `ImportError` (переименована `get_service_keyboard`) в `handlers/booking/booking.py`
*   [x] `AttributeError` в `get_dates_keyboard` (неверные аргументы)
*   [x] `ImportError` (перемещен `calendar_utils`)
*   [x] `ModuleNotFoundError: No module named 'dotenv'`
*   [x] `NameError: name 'handle_calendar_action' is not defined`

---

## Новые и неисправленные

*   [ ] **⚠️ FSM MemoryStorage не персистентен:** Состояния пользователей теряются при перезагрузке. Требуется переход на Redis или другое постоянное хранилище. 
*   [ ] **⚠️ `handle_calendar_action` требует восстановления:** Функция была закомментирована для запуска. Необходимо восстановить логику навигации по календарю.
*   [ ] **⚠️ `setup.py` DBManager `super()` error:** Потенциальная проблема с вызовом `super().__init__()` в конструкторе `DBManager`, которая может проявиться позже.
