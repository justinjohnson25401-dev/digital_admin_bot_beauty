
import sqlite3
import logging

logger = logging.getLogger(__name__)

LATEST_SCHEMA_VERSION = 3

# Белый список таблиц для защиты от SQL injection
ALLOWED_TABLES = {'orders', 'users', 'schema_migrations'}

class Database:
    def __init__(self, business_slug: str):
        self.db_path = f"db_{business_slug}.sqlite"
        self.connection = None

    def _ensure_connection(self):
        """Проверка и восстановление соединения с БД"""
        if not self.connection:
            raise RuntimeError("Database not initialized. Call init_db() first.")
        try:
            self.connection.execute("SELECT 1")
        except sqlite3.Error:
            logger.warning("DB connection lost, reconnecting...")
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            try:
                self.connection.execute("PRAGMA foreign_keys = ON")
                self.connection.execute("PRAGMA busy_timeout = 5000")
                self.connection.execute("PRAGMA journal_mode = WAL")
                self.connection.execute("PRAGMA synchronous = NORMAL")
            except Exception:
                pass

    def _table_exists(self, cursor, table_name: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def _column_exists(self, cursor, table_name: str, column_name: str) -> bool:
        if table_name not in ALLOWED_TABLES:
            logger.error(f"Invalid table name: {table_name}")
            return False
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            cols = cursor.fetchall()
            return any(row[1] == column_name for row in cols)
        except sqlite3.Error:
            return False

    def _get_schema_version(self, cursor) -> int:
        if not self._table_exists(cursor, 'schema_migrations'):
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER NOT NULL)"
            )
            cursor.execute("DELETE FROM schema_migrations")
            cursor.execute("INSERT INTO schema_migrations(version) VALUES (0)")
            return 0

        cursor.execute("SELECT version FROM schema_migrations LIMIT 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO schema_migrations(version) VALUES (0)")
            return 0
        try:
            return int(row[0] or 0)
        except Exception:
            return 0

    def _set_schema_version(self, cursor, version: int) -> None:
        cursor.execute("DELETE FROM schema_migrations")
        cursor.execute("INSERT INTO schema_migrations(version) VALUES (?)", (int(version),))

    def _apply_migrations(self, cursor) -> None:
        current_version = self._get_schema_version(cursor)
        target_version = LATEST_SCHEMA_VERSION

        if current_version >= target_version:
            return

        logger.info(f"Applying DB migrations: {current_version} -> {target_version}")

        if current_version < 1:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    service_id TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    client_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    comment TEXT,
                    booking_date TEXT,
                    booking_time TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL
                )
                """
            )

            if self._table_exists(cursor, 'orders') and not self._column_exists(cursor, 'orders', 'comment'):
                cursor.execute("ALTER TABLE orders ADD COLUMN comment TEXT")

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_booking_slot
                ON orders(booking_date, booking_time, status)
                """
            )

            self._set_schema_version(cursor, 1)

        current_version = self._get_schema_version(cursor)
        if current_version < 2:
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_user_created
                ON orders(user_id, created_at)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_status_booking_date
                ON orders(status, booking_date)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_user_id
                ON users(user_id)
                """
            )

            self._set_schema_version(cursor, 2)

        current_version = self._get_schema_version(cursor)
        if current_version < 3:
            # Добавление колонки master_id для поддержки персонала
            if not self._column_exists(cursor, 'orders', 'master_id'):
                cursor.execute("ALTER TABLE orders ADD COLUMN master_id TEXT")
                logger.info("Added master_id column to orders table")

            # Индекс для поиска по мастеру
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_master_id
                ON orders(master_id, booking_date, booking_time)
                """
            )

            self._set_schema_version(cursor, 3)

        current_version = self._get_schema_version(cursor)
        if current_version < target_version:
            raise RuntimeError(
                f"Database schema migration did not reach target version: {current_version} != {target_version}"
            )

    def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            try:
                self.connection.execute("PRAGMA foreign_keys = ON")
            except Exception:
                pass
            try:
                self.connection.execute("PRAGMA busy_timeout = 5000")
            except Exception:
                pass
            try:
                self.connection.execute("PRAGMA journal_mode = WAL")
            except Exception:
                pass
            try:
                self.connection.execute("PRAGMA synchronous = NORMAL")
            except Exception:
                pass
            cursor = self.connection.cursor()

            self._apply_migrations(cursor)

            self.connection.commit()
            logger.info(f"Database initialized: {self.db_path}")

            try:
                cursor2 = self.connection.cursor()
                version_after = self._get_schema_version(cursor2)
                logger.info(f"Database schema version: {version_after}")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Database initialization/migration error: {e}")
            logger.error(
                "Database is not usable. Recommended actions:\n"
                "1) Check DB schema/version: sudo bash deploy/linux/db_info.sh\n"
                "2) Restore from backup:     sudo bash deploy/linux/restore.sh\n"
                "3) If issue persists: check disk space/permissions for db_*.sqlite"
            )
            try:
                if self.connection:
                    self.connection.rollback()
            except Exception:
                pass
            try:
                if self.connection:
                    self.connection.close()
            except Exception:
                pass
            self.connection = None
            raise

    def close(self):
        """Закрытие соединения с БД"""
        if self.connection:
            self.connection.close()
            logger.info(f"Database connection closed: {self.db_path}")

