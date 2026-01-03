
import sqlite3
import logging

from utils.db.booking_queries import BookingQueries

logger = logging.getLogger(__name__)

class StaffQueries(BookingQueries):

    def __init__(self, db_connection):
        super().__init__(db_connection)
        self.connection = db_connection

    def _ensure_connection(self):
        if not self.connection:
            raise RuntimeError("Database not initialized.")
        try:
            self.connection.execute("SELECT 1")
        except sqlite3.Error:
            raise RuntimeError("Database connection lost.")

    def check_slot_availability(self, booking_date: str, booking_time: str, exclude_order_id: int = None) -> bool:
        """Проверка доступности слота (опционально для конкретного мастера)"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            query = """
                SELECT COUNT(*) FROM orders
                WHERE booking_date = ? AND booking_time = ? AND status = 'active'
            """
            params = [booking_date, booking_time]

            if exclude_order_id:
                query += " AND id != ?"
                params.append(exclude_order_id)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            return count == 0

        except sqlite3.Error as e:
            logger.error(f"Error checking slot availability: {e}")
            return False

    def get_occupied_slots_for_master(self, booking_date: str, master_id: str) -> list:
        """Получить список занятых слотов мастера на дату"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT booking_time FROM orders
                WHERE booking_date = ? AND master_id = ? AND status = 'active'
            """, (booking_date, master_id))

            return [row[0] for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error getting occupied slots for master: {e}")
            return []

    def check_slot_availability_for_master(self, booking_date: str, booking_time: str, master_id: str, exclude_order_id: int = None) -> bool:
        """Проверка доступности слота для конкретного мастера (алиас)"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            query = """
                SELECT COUNT(*) FROM orders
                WHERE booking_date = ? AND booking_time = ? AND master_id = ? AND status = 'active'
            """
            params = [booking_date, booking_time, master_id]

            if exclude_order_id:
                query += " AND id != ?"
                params.append(exclude_order_id)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            return count == 0
        except sqlite3.Error as e:
            logger.error(f"Error checking slot availability for master: {e}")
            return False

    def check_slot_availability_excluding(
        self,
        booking_date: str,
        booking_time: str,
        exclude_order_id: int
    ) -> bool:
        """
        Проверяет, свободен ли слот (дата + время) для бронирования,
        исключая из проверки существующий заказ exclude_order_id (при редактировании).
        """
        try:
            self._ensure_connection()

            # Получаем информацию о редактируемом заказе для определения мастера
            order = self.get_order_by_id(exclude_order_id)
            master_id = order.get('master_id') if order else None

            cursor = self.connection.cursor()

            if master_id:
                cursor.execute("""
                    SELECT COUNT(*) FROM orders
                    WHERE booking_date = ?
                      AND booking_time = ?
                      AND master_id = ?
                      AND status = 'active'
                      AND id != ?
                """, (booking_date, booking_time, master_id, exclude_order_id))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM orders
                    WHERE booking_date = ?
                      AND booking_time = ?
                      AND status = 'active'
                      AND id != ?
                """, (booking_date, booking_time, exclude_order_id))

            count = cursor.fetchone()[0]
            return count == 0

        except sqlite3.Error as e:
            logger.error(f"Error checking slot availability excluding order {exclude_order_id}: {e}")
            return False
