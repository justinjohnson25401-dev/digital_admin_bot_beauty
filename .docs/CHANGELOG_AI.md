# 🤖 CHANGELOG (AI-Managed)

## 2026-01-04

### REFACTOR
- **Refactored `mybookings.py` Handler:**
  - **Before:** A monolithic 668-line file (`handlers/mybookings.py`) handled viewing, canceling, and rescheduling bookings, making it hard to maintain.
  - **After:** The logic was split into a dedicated package `handlers/mybookings/` with clear, single-responsibility modules:
    - `view.py`: Handles displaying user bookings.
    - `cancel.py`: Manages the booking cancellation process.
    - `reschedule.py`: Contains logic for modifying existing bookings (date, time, service).
    - `keyboards.py`: Centralizes keyboard generation for the feature.
    - `__init__.py`: Aggregates the new routers.
  - **Impact:** Improved code modularity, readability, and maintainability.

### FIX
- **Persistent FSM Storage:**
  - **Before:** FSM states were stored in memory (`MemoryStorage`), causing all user states to be lost on bot restart.
  - **After:** Implemented `SQLiteStorage` in `main.py` to persist FSM states across restarts. The storage path is now `fsm_data_{business_slug}.db`.
  - **Impact:** Enhanced user experience by preserving their progress in multi-step interactions.

- **Critical Race Condition in Booking:**
  - **Before:** A race condition allowed two users to book the same time slot simultaneously.
  - **After:** The `add_order` method in `utils/db/booking_queries.py` was wrapped in a `with self.connection:` block, ensuring the `check_slot` and `INSERT` operations are atomic.
  - **Impact:** Prevents double bookings and ensures data integrity.

---

## 2026-01-03

### REFACTOR

- **Refactored `booking.py` Handler:**
  - **Before:** The file `handlers/booking.py` was a large, monolithic module responsible for the entire booking process.
  - **After:** The handler was split into a `booking` package (`/handlers/booking/`) with specialized modules:
    - `appointment.py`: Core booking logic (date, time, service selection).
    - `calendar_utils.py`: Calendar generation and navigation.
    - `keyboards.py`: Keyboard layouts.
    - `confirmation.py`: Final booking confirmation.
    - `__init__.py`: Aggregates the new, modular routers.
  - **Impact:** Improved code organization and maintainability.

- **Refactored `DBManager` Class:**
  - **Before:** `DBManager` was a monolithic class handling both DB connection and all SQL queries, leading to poor separation of concerns.
  - **After:** The class was split. `DBManager` now only manages the connection, while all query logic has been moved to specialized modules within the `utils/db/` package (`user_queries.py`, `booking_queries.py`, etc.).
  - **Impact:** Better code structure, easier to test and maintain.
