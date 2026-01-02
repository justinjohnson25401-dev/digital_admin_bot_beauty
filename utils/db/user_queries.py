
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class UserQueries:

    def __init__(self, db_connection):
        self.connection = db_connection

    def _ensure_connection(self):
        if not self.connection:
            raise RuntimeError("Database not initialized.")
        try:
            self.connection.execute("SELECT 1")
        except sqlite3.Error:
            # The connection should be managed by the Database class
            raise RuntimeError("Database connection lost.")

    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Добавление или обновление пользователя"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            created_at = datetime.now().isoformat()

            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, created_at))

            self.connection.commit()

        except sqlite3.Error as e:
            logger.error(f"Error adding user: {e}")

    def get_last_client_details(self, user_id: int) -> dict | None:
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT client_name, phone
                FROM orders
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {'client_name': row[0], 'phone': row[1]}
        except sqlite3.Error as e:
            logger.error(f"Error getting last client details: {e}")
            return None
