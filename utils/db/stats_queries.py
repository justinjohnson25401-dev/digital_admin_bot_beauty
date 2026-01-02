
import sqlite3
import logging
from datetime import datetime, timedelta
from io import StringIO
import csv

logger = logging.getLogger(__name__)

class StatsQueries:

    def __init__(self, db_connection):
        self.connection = db_connection

    def _ensure_connection(self):
        if not self.connection:
            raise RuntimeError("Database not initialized.")
        try:
            self.connection.execute("SELECT 1")
        except sqlite3.Error:
            raise RuntimeError("Database connection lost.")

    def get_stats(self, period: str = 'today') -> dict:
        """Получение статистики с защитой от SQL injection"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()

            ALLOWED_PERIODS = {'today', 'week', 'month'}
            if period not in ALLOWED_PERIODS:
                logger.warning(f"Invalid period: {period}, using 'today'")
                period = 'today'

            if period == 'today':
                days_back = 0
            elif period == 'week':
                days_back = 7
            else:  # month
                days_back = 30

            cutoff_date = (datetime.now() - timedelta(days=days_back)).date().isoformat()

            cursor.execute("""
                SELECT COUNT(*) FROM orders
                WHERE created_at >= ? AND status = 'active'
            """, (cutoff_date,))
            total_orders = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM orders
                WHERE created_at >= ? AND status = 'active'
                AND booking_date > date('now')
            """, (cutoff_date,))
            planned_orders = cursor.fetchone()[0]

            cursor.execute("""
                SELECT service_name, COUNT(*) as count
                FROM orders
                WHERE created_at >= ? AND status = 'active'
                GROUP BY service_name
                ORDER BY count DESC
                LIMIT 5
            """, (cutoff_date,))
            top_services = cursor.fetchall()

            cursor.execute("""
                SELECT SUM(price) FROM orders
                WHERE created_at >= ? AND status = 'active'
                AND (booking_date IS NULL OR booking_date <= date('now'))
            """, (cutoff_date,))
            total_revenue = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT SUM(price) FROM orders
                WHERE created_at >= ? AND status = 'active'
                AND booking_date > date('now')
            """, (cutoff_date,))
            planned_revenue = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= ?
            """, (cutoff_date,))
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
            return {
                'total_orders': 0,
                'planned_orders': 0,
                'top_services': [],
                'total_revenue': 0,
                'planned_revenue': 0,
                'new_clients': 0
            }

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

    def get_statistics_by_period(self, start_date: str, end_date: str) -> dict:
        """
        Получить статистику за указанный период
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
