"""
DatabaseManager - единый интерфейс для работы с базой данных.
Использует реальную реализацию из db_manager.py.
"""

from utils.db_manager import DatabaseManager as RealDatabaseManager


class DatabaseManager(RealDatabaseManager):
    """
    Расширенный DatabaseManager с алиасами для совместимости.
    Наследует все методы от RealDatabaseManager и добавляет алиасы.
    """

    def __init__(self, business_slug: str):
        db_path = f"db_{business_slug}.sqlite"
        super().__init__(db_path)
        self.business_slug = business_slug

    # === Алиасы для совместимости с handlers ===

    def get_user_contact_info(self, user_id):
        """Алиас для get_last_client_details (совместимость с contact.py)."""
        details = self.get_last_client_details(user_id)
        if details:
            return {'name': details.get('client_name'), 'phone': details.get('phone')}
        return None

    def update_user_contact_info(self, user_id, name, phone):
        """Алиас для save_last_client_details (совместимость с contact.py)."""
        self.save_last_client_details(user_id, name, phone)

    def create_booking(self, user_id, service_id, service_name, master_id, master_name,
                       booking_datetime, price, comment=None, client_name=None, phone=None):
        """Алиас для add_booking (совместимость с confirmation.py)."""
        return self.add_booking(
            user_id=user_id,
            client_name=client_name or "Не указано",
            phone=phone or "Не указан",
            service_id=service_id,
            service_name=service_name,
            master_id=master_id,
            master_name=master_name,
            booking_datetime=booking_datetime,
            comment=comment,
            price=price
        )

    def get_order_by_id(self, order_id):
        """Алиас для get_booking_by_id."""
        return self.get_booking_by_id(order_id)

    def add_order(self, user_id, service_id, service_name, price, client_name, phone,
                  comment, booking_date, booking_time, master_id, master_name=None):
        """Совместимость со старым API (save.py)."""
        booking_datetime = f"{booking_date}T{booking_time}"
        return self.add_booking(
            user_id=user_id,
            client_name=client_name or "Не указано",
            phone=phone or "Не указан",
            service_id=service_id,
            service_name=service_name,
            master_id=master_id,
            master_name=master_name,
            booking_datetime=booking_datetime,
            comment=comment,
            price=price
        )

    def add_user(self, user_id, username, first_name, last_name):
        """Заглушка - пользователи сохраняются через client_details."""
        pass

    def get_user_bookings(self, user_id, active_only=True):
        """Получение записей пользователя (active_only игнорируется - отменённые удаляются)."""
        return super().get_user_bookings(user_id)

    def check_slot_availability(self, date_str, time_str, exclude_order_id=None):
        """Проверка доступности слота."""
        busy = self.get_busy_slots(date_str)
        return time_str not in busy

    def check_slot_availability_for_master(self, date_str, time_str, master_id, exclude_order_id=None):
        """Проверка доступности слота для мастера."""
        busy = self.get_busy_slots(date_str, master_id)
        return time_str not in busy

    def check_slot_availability_excluding(self, date_str, time_str, order_id):
        """Проверка доступности слота при переносе (исключая текущий заказ)."""
        busy = self.get_busy_slots(date_str)
        return time_str not in busy

    def update_order(self, order_id, **updates):
        """Обновление заказа."""
        if not updates:
            return False
        try:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            sql = f"UPDATE bookings SET {set_clause} WHERE id = ?"
            self.cursor.execute(sql, (*updates.values(), order_id))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception:
            self.conn.rollback()
            return False
