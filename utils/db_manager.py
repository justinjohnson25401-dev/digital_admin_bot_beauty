import sqlite3
import logging
from datetime import datetime, timedelta
from io import StringIO
import csv
from .privacy import safe_log_order_creation

logger = logging.getLogger(__name__)

LATEST_SCHEMA_VERSION = 3

# Белый список таблиц для защиты от SQL injection
ALLOWED_TABLES = {'orders', 'users', 'schema_migrations'}

class DBManager:
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

    def add_order(self, user_id: int, service_id: str, service_name: str, price: int,
                  client_name: str, phone: str, comment: str = None,
                  booking_date: str = None, booking_time: str = None,
                  master_id: str = None) -> int:
        """Добавление заказа с защитой от race condition"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            created_at = datetime.now().isoformat()

            # Защита от race condition: проверяем доступность слота в транзакции
            if booking_date and booking_time:
                if master_id:
                    # Если указан мастер, проверяем слот только для этого мастера
                    cursor.execute("""
                        SELECT COUNT(*) FROM orders
                        WHERE booking_date = ? AND booking_time = ? AND master_id = ? AND status = 'active'
                    """, (booking_date, booking_time, master_id))
                else:
                    # Если мастер не указан, проверяем общую доступность
                    cursor.execute("""
                        SELECT COUNT(*) FROM orders
                        WHERE booking_date = ? AND booking_time = ? AND status = 'active'
                    """, (booking_date, booking_time))
                if cursor.fetchone()[0] > 0:
                    raise ValueError(f"Слот {booking_date} {booking_time} уже занят")

            cursor.execute("""
                INSERT INTO orders (user_id, service_id, service_name, price, client_name, phone,
                                   comment, booking_date, booking_time, master_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """, (user_id, service_id, service_name, price, client_name, phone,
                  comment, booking_date, booking_time, master_id, created_at))

            self.connection.commit()
            order_id = cursor.lastrowid

            # Безопасное логирование с маскировкой персональных данных
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
            logger.warning(f"Slot already taken: {e}")
            raise
        except sqlite3.Error as e:
            logger.error(f"Error adding order: {e}")
            raise

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

    # ИЗМЕНЕНО: Добавлена поддержка параметра active_only и master_id
    def get_user_bookings(self, user_id: int, active_only: bool = True) -> list:
        """Получение списка записей пользователя"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            if active_only:
                # Только активные записи с master_id
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
        """Получение информации о заказе по ID (включая master_id)"""
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
        """Обновление полей заказа (включая master_id)"""
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

    def get_stats(self, period: str = 'today') -> dict:
        """Получение статистики с разделением на текущую и планируемую выручку"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            if period == 'today':
                date_filter = "date('now')"
            elif period == 'week':
                date_filter = "date('now', '-7 days')"
            else:
                date_filter = "date('now', '-30 days')"

            # Количество заявок (все)
            cursor.execute(f"""
                SELECT COUNT(*) FROM orders
                WHERE created_at >= {date_filter} AND status = 'active'
            """)
            total_orders = cursor.fetchone()[0]

            # Количество будущих заявок (booking_date > today)
            cursor.execute(f"""
                SELECT COUNT(*) FROM orders
                WHERE created_at >= {date_filter} AND status = 'active'
                AND booking_date > date('now')
            """)
            planned_orders = cursor.fetchone()[0]

            # Топ услуг
            cursor.execute(f"""
                SELECT service_name, COUNT(*) as count
                FROM orders
                WHERE created_at >= {date_filter} AND status = 'active'
                GROUP BY service_name
                ORDER BY count DESC
                LIMIT 5
            """)
            top_services = cursor.fetchall()

            # Выручка от завершённых/сегодняшних заказов (booking_date <= today)
            cursor.execute(f"""
                SELECT SUM(price) FROM orders
                WHERE created_at >= {date_filter} AND status = 'active'
                AND (booking_date IS NULL OR booking_date <= date('now'))
            """)
            total_revenue = cursor.fetchone()[0] or 0

            # Планируемая выручка (будущие заказы: booking_date > today)
            cursor.execute(f"""
                SELECT SUM(price) FROM orders
                WHERE created_at >= {date_filter} AND status = 'active'
                AND booking_date > date('now')
            """)
            planned_revenue = cursor.fetchone()[0] or 0

            # Новых клиентов за период
            cursor.execute(f"""
                SELECT COUNT(*) FROM users
                WHERE created_at >= {date_filter}
            """)
            new_clients = cursor.fetchone()[0]

            return {
                'total_orders': total_orders,
                'planned_orders': planned_orders,
                'top_services': [(name, count) for name, count in top_services],
                'total_revenue': total_revenue,
                'planned_revenue': planned_revenue,
                'new_clients': new_clients
            }

        except sqlite3.Error as e:
            logger.error(f"Error getting stats: {e}")
            return {'total_orders': 0, 'planned_orders': 0, 'top_services': [], 'total_revenue': 0, 'planned_revenue': 0, 'new_clients': 0}

    def get_orders_csv(self, days: int = 30) -> bytes:
        """Получение заказов за последние N дней в формате CSV"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute("""
                SELECT id, user_id, service_id, service_name, price, client_name, phone,
                       comment, booking_date, booking_time, status, created_at
                FROM orders
                WHERE created_at >= ?
                ORDER BY created_at DESC
            """, (cutoff_date,))

            rows = cursor.fetchall()
            output = StringIO()
            writer = csv.writer(output, delimiter=';')

            writer.writerow(['ID', 'User ID', 'Service ID', 'Service Name', 'Price',
                           'Client Name', 'Phone', 'Comment', 'Booking Date',
                           'Booking Time', 'Status', 'Created At'])

            for row in rows:
                writer.writerow(row)

            csv_content = output.getvalue()
            output.close()

            return csv_content.encode('utf-8-sig')

        except sqlite3.Error as e:
            logger.error(f"Error generating CSV: {e}")
            raise

    def close(self):
        """Закрытие соединения с БД"""
        if self.connection:
            self.connection.close()
            logger.info(f"Database connection closed: {self.db_path}")

    def get_statistics_by_period(self, start_date: str, end_date: str) -> dict:
        """
        Получить статистику за указанный период
        
        :param start_date: Начальная дата (YYYY-MM-DD)
        :param end_date: Конечная дата (YYYY-MM-DD)
        :return: Словарь со статистикой
        """
        cursor = self.connection.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                SUM(CASE WHEN status = 'completed' THEN price ELSE 0 END) as revenue
            FROM orders
            WHERE booking_date >= ? AND booking_date <= ?
        """, (start_date, end_date))
        
        row = cursor.fetchone()
        
        return {
            'total_bookings': row[0] or 0,
            'completed': row[1] or 0,
            'cancelled': row[2] or 0,
            'revenue': row[3] or 0
        }
