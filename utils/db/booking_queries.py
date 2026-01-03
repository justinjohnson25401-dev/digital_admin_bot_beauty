
import sqlite3
import logging
from datetime import datetime
from utils.privacy import safe_log_order_creation

logger = logging.getLogger(__name__)

class BookingQueries:

    def __init__(self, db_connection):
        self.connection = db_connection

    def _ensure_connection(self):
        if not self.connection:
            raise RuntimeError("Database not initialized.")
        try:
            self.connection.execute("SELECT 1")
        except sqlite3.Error:
            raise RuntimeError("Database connection lost.")

    def add_order(self, user_id: int, service_id: str, service_name: str, price: int,
                  client_name: str, phone: str, comment: str = None,
                  booking_date: str = None, booking_time: str = None,
                  master_id: str = None) -> int:
        """Добавление заказа с защитой от race condition"""
        try:
            self._ensure_connection()
            # Используем `with self.connection` для атомарной транзакции
            with self.connection:
                cursor = self.connection.cursor()
                created_at = datetime.now().isoformat()

                # Шаг 1: Проверяем доступность слота
                if booking_date and booking_time:
                    if master_id:
                        cursor.execute("""
                            SELECT COUNT(*) FROM orders
                            WHERE booking_date = ? AND booking_time = ? AND master_id = ? AND status = 'active'
                        """, (booking_date, booking_time, master_id))
                    else:
                        cursor.execute("""
                            SELECT COUNT(*) FROM orders
                            WHERE booking_date = ? AND booking_time = ? AND status = 'active'
                        """, (booking_date, booking_time))
                    
                    if cursor.fetchone()[0] > 0:
                        raise ValueError(f"Слот {booking_date} {booking_time} уже занят")

                # Шаг 2: Создаем заказ (если слот свободен)
                cursor.execute("""
                    INSERT INTO orders (user_id, service_id, service_name, price, client_name, phone,
                                       comment, booking_date, booking_time, master_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                """, (user_id, service_id, service_name, price, client_name, phone,
                      comment, booking_date, booking_time, master_id, created_at))

                order_id = cursor.lastrowid

            # Контекстный менеджер `with` автоматически сохраняет изменения (commit)
            # или откатывает их (rollback) в случае ошибки.

            log_msg = safe_log_order_creation(
                user_id=user_id,
                service_name=service_name,
                client_name=client_name,
                phone=phone,
                booking_date=booking_date,
                booking_time=booking_time
            )
            master_info = f", master_id={master_id}" if master_id else ""
            logger.info(f"ID={order_id}, {log_msg}{master_info}")

            return order_id

        except ValueError as e:
            # Ошибка (слот занят) будет обработана, транзакция автоматически отменена
            logger.warning(f"Slot already taken: {e}")
            raise
        except sqlite3.Error as e:
            # Ошибка БД, транзакция автоматически отменена
            logger.error(f"Error adding order: {e}")
            raise

    def get_user_bookings(self, user_id: int, active_only: bool = True) -> list:
        """Получение списка записей пользователя"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            if active_only:
                cursor.execute("""
                    SELECT id, service_name, booking_date, booking_time, price, status,
                           created_at, comment, client_name, phone, master_id
                    FROM orders
                    WHERE user_id = ? AND status = 'active'
                      AND (booking_date IS NULL OR booking_date >= date('now'))
                    ORDER BY COALESCE(booking_date, date('now')), booking_time
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT id, service_name, booking_date, booking_time, price, status,
                           created_at, comment, client_name, phone, master_id
                    FROM orders
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """, (user_id,))

            rows = cursor.fetchall()
            bookings = []

            for row in rows:
                bookings.append({
                    'id': row[0],
                    'service_name': row[1],
                    'booking_date': row[2],
                    'booking_time': row[3],
                    'price': row[4],
                    'status': row[5],
                    'created_at': row[6],
                    'comment': row[7] if len(row) > 7 else None,
                    'client_name': row[8] if len(row) > 8 else None,
                    'phone': row[9] if len(row) > 9 else None,
                    'master_id': row[10] if len(row) > 10 else None
                })

            return bookings

        except sqlite3.Error as e:
            logger.error(f"Error getting user bookings: {e}")
            return []

    def get_order_by_id(self, order_id: int) -> dict:
        """Получение информации о заказе по ID"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, user_id, service_id, service_name, price, booking_date, booking_time,
                       client_name, phone, comment, status, master_id
                FROM orders
                WHERE id = ?
            """, (order_id,))

            row = cursor.fetchone()

            if row:
                return {
                    'id': row[0],
                    'user_id': row[1],
                    'service_id': row[2],
                    'service_name': row[3],
                    'price': row[4],
                    'booking_date': row[5],
                    'booking_time': row[6],
                    'client_name': row[7],
                    'phone': row[8],
                    'comment': row[9],
                    'status': row[10],
                    'master_id': row[11] if len(row) > 11 else None
                }

            return None

        except sqlite3.Error as e:
            logger.error(f"Error getting order by ID: {e}")
            return None

    def update_order(self, order_id: int, **kwargs) -> bool:
        """Обновление полей заказа"""
        try:
            self._ensure_connection()
            set_parts = []
            values = []
            allowed_fields = ['service_id', 'service_name', 'price', 'booking_date',
                            'booking_time', 'client_name', 'phone', 'comment', 'master_id']

            for field, value in kwargs.items():
                if field in allowed_fields:
                    set_parts.append(f"{field} = ?")
                    values.append(value)

            if not set_parts:
                logger.warning("No valid fields to update")
                return False

            values.append(order_id)
            cursor = self.connection.cursor()
            query = f"UPDATE orders SET {', '.join(set_parts)} WHERE id = ?"
            cursor.execute(query, values)
            self.connection.commit()

            logger.info(f"Order {order_id} updated: {kwargs}")
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error updating order: {e}")
            return False

    def cancel_order(self, order_id: int) -> bool:
        """Отмена заказа"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cursor.execute("""
                UPDATE orders SET status = 'cancelled' WHERE id = ?
            """, (order_id,))

            self.connection.commit()
            logger.info(f"Order {order_id} cancelled")
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def get_active_orders_for_reminders(self) -> list:
        """Получение активных заказов для системы напоминаний"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, user_id, service_name, booking_date, booking_time
                FROM orders
                WHERE status = 'active' AND booking_date >= date('now')
                ORDER BY booking_date, booking_time
            """)

            rows = cursor.fetchall()
            orders = []

            for row in rows:
                orders.append({
                    'id': row[0],
                    'user_id': row[1],
                    'service_name': row[2],
                    'booking_date': row[3],
                    'booking_time': row[4]
                })

            return orders

        except sqlite3.Error as e:
            logger.error(f"Error getting orders for reminders: {e}")
            return []
