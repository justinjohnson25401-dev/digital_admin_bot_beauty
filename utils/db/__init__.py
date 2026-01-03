import logging
from contextlib import contextmanager

from .database import Database
from .user_queries import UserQueries
from .booking_queries import BookingQueries
from .stats_queries import StatsQueries
from .staff_queries import StaffQueries

logger = logging.getLogger(__name__)

class DatabaseManager:

    def __init__(self, business_slug: str):
        self.db = Database(business_slug)
        self.db.init_db()

        self.users = UserQueries(self.db.connection)
        self.bookings = BookingQueries(self.db.connection)
        self.stats = StatsQueries(self.db.connection)
        self.staff = StaffQueries(self.db.connection)

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для безопасного получения соединения с БД."""
        if not self.db.connection:
            logger.error("DB connection not available upon entering context")
            raise RuntimeError("Database not initialized or connection lost.")

        try:
            # Проверяем живо ли соединение
            self.db._ensure_connection()
            yield self.db.connection
        except Exception as e:
            logger.error(f"Error within DB context: {e}", exc_info=True)
            # В случае ошибки соединение может быть уже закрыто или повреждено,
            # поэтому явный rollback здесь может быть не нужен или невозможен.
            # self.db.connection.rollback()
            raise
        # `commit` и `rollback` должны управляться кодом, использующим соединение

    def close(self):
        """Закрывает соединение с базой данных."""
        self.db.close()

    def reinitialize(self):
        """Переинициализирует соединение с базой данных."""
        logger.info("Reinitializing database connection...")
        self.close()
        self.db.init_db()
        self.users = UserQueries(self.db.connection)
        self.bookings = BookingQueries(self.db.connection)
        self.stats = StatsQueries(self.db.connection)
        self.staff = StaffQueries(self.db.connection)
        logger.info("Database connection reinitialized.")
