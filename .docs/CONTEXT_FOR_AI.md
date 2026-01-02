# 🧠 CONTEXT FOR AI

## Project Overview

- **Project:** Telegram Bot for Business (V2)
- **Purpose:** A modular and configurable Telegram bot designed to help small businesses manage client bookings, appointments, and showcase their services.
- **Key Technologies:** Python, `aiogram` (v3+), SQLite.
- **Core Principles:** Modularity, Configurability, Separation of Concerns.

---

## Codebase Structure

- **`main.py`:**
  - **Entry point** of the application.
  - Initializes the bot, dispatcher, database (`DBManager`), FSM storage (`SQLiteStorage`), and configuration.
  - Sets up middleware for dependency injection (config, db_manager).
  - **Dynamically loads configuration** from the `/config` directory and watches for changes.
  - Registers all routers from the `handlers` packages.

- **`handlers/`:**
  - **Contains all user-facing logic** organized into packages (routers).
  - **`handlers/start.py`**: Handles the `/start` command and main menu navigation.
  - **`handlers/booking/`**: A package for the new booking process.
    - Logic is split into `appointment.py`, `calendar_utils.py`, `confirmation.py`, etc.
  - **`handlers/mybookings/`**: A package for managing existing bookings.
    - `view.py`: Display user's bookings.
    - `cancel.py`: Cancel a booking.
    - `reschedule.py`: Edit a booking (date, time, service).

- **`utils/`:**
  - **`utils/config_loader.py`**: Merges multiple JSON config files from a directory into a single dictionary.
  - **`utils/db/`**: Database management package.
    - **`db_manager.py`**: The `DBManager` class, responsible *only* for connection management and initialization.
    - **`*_queries.py`**: Modules containing specific SQL query functions (e.g., `booking_queries.py`, `user_queries.py`). Queries are separated by domain.
  - **`utils/notify.py`**: Functions for sending notifications to administrators.

- **`states/`:**
  - **`states/booking.py`**: Defines all `aiogram` FSM (Finite State Machine) states for the booking and editing processes.

- **`config/`:**
  - **MUST NOT BE MODIFIED BY THE AI.**
  - Directory containing user-defined `.json` configuration files. The AI should read from here but never write.

- **`.docs/`:**
  - **AI-managed documentation.** Contains files like this one, `CHANGELOG_AI.md`, `BUGS_TRACKER.md`, and `PROJECT_STATE.md` to track the development process.

---

## Key Architectural Decisions

1.  **Modular Routers:** Instead of large, monolithic handler files, logic is split into `aiogram` `Router`s, often grouped into packages for major features (e.g., `booking`, `mybookings`).
2.  **Separation of Concerns in DB Layer:** The `DBManager` handles *how* to connect, while the `*_queries.py` modules handle *what* to query. This makes the code cleaner and easier to test.
3.  **Dynamic Configuration:** The bot can be reconfigured without a restart by simply changing the JSON files in the `/config` directory. `main.py` handles hot-reloading.
4.  **Persistent FSM:** `SQLiteStorage` is used to ensure user states in conversations are not lost if the bot restarts.
5.  **AI-Driven Development:** An AI assistant (like me) is responsible for writing, refactoring, and documenting code. The `.docs` directory is the AI's primary workspace for tracking tasks and changes.
