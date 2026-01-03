"""
Тесты для DatabaseManager.
"""

import pytest
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import DatabaseManager


class TestDatabaseManager:
    """Тесты для DatabaseManager."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Создать временную базу данных для каждого теста."""
        self.original_dir = os.getcwd()
        os.chdir(tmp_path)
        self.db = DatabaseManager('test_db')
        yield
        self.db.close()
        os.chdir(self.original_dir)

    def test_init_db_creates_tables(self):
        """БД должна создать все нужные таблицы."""
        cursor = self.db.db.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        expected_tables = {'orders', 'users'}
        assert expected_tables.issubset(tables)

    def test_add_order(self):
        """Должен добавлять заказ."""
        order_id = self.db.bookings.add_order(
            user_id=123456789,
            service_id='service1',
            service_name='Стрижка',
            price=1000,
            client_name='Тест Клиент',
            phone='+79001234567',
            comment='Тестовый комментарий',
            booking_date=datetime.now().date().isoformat(),
            booking_time='10:00'
        )
        assert order_id is not None
        assert order_id > 0

    def test_get_order_by_id(self):
        """Должен получать заказ по ID."""
        order_id = self.db.bookings.add_order(
            user_id=123456789,
            service_id='service1',
            service_name='Маникюр',
            price=1500,
            client_name='Клиент',
            phone='+79001234567',
            booking_date=datetime.now().date().isoformat(),
            booking_time='14:00'
        )
        order = self.db.bookings.get_order_by_id(order_id)
        assert order is not None
        assert order['id'] == order_id
        assert order['service_name'] == 'Маникюр'
        assert order['price'] == 1500

    def test_check_slot_availability(self):
        """Проверка доступности слота."""
        booking_date = datetime.now().date().isoformat()
        booking_time = '15:00'

        # Слот должен быть свободен
        assert self.db.staff.check_slot_availability(booking_date, booking_time) is True

        # Добавляем заказ
        self.db.bookings.add_order(
            user_id=123,
            service_id='s1',
            service_name='Тест',
            price=100,
            client_name='Тест',
            phone='+79001111111',
            booking_date=booking_date,
            booking_time=booking_time
        )

        # Теперь слот занят
        assert self.db.staff.check_slot_availability(booking_date, booking_time) is False

    def test_cancel_order(self):
        """Должен отменять заказ."""
        order_id = self.db.bookings.add_order(
            user_id=123,
            service_id='s1',
            service_name='Тест',
            price=100,
            client_name='Тест',
            phone='+79001111111',
            booking_date=datetime.now().date().isoformat(),
            booking_time='16:00'
        )
        result = self.db.bookings.cancel_order(order_id)
        assert result is True
        order = self.db.bookings.get_order_by_id(order_id)
        assert order['status'] == 'cancelled'

    def test_get_user_bookings(self):
        """Должен возвращать записи пользователя."""
        user_id = 999888777
        self.db.bookings.add_order(
            user_id=user_id, service_id='s1', service_name='Услуга 1',
            price=100, client_name='Клиент', phone='+79001111111',
            booking_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
            booking_time='10:00'
        )
        self.db.bookings.add_order(
            user_id=user_id, service_id='s2', service_name='Услуга 2',
            price=200, client_name='Клиент', phone='+79001111111',
            booking_date=(datetime.now() + timedelta(days=2)).date().isoformat(),
            booking_time='11:00'
        )
        bookings = self.db.bookings.get_user_bookings(user_id, active_only=True)
        assert len(bookings) >= 2
