import pytest
import tempfile
import os
from utils.db_manager import DBManager

@pytest.fixture
def db():
    """Создаём временную БД для тестов"""
    # Используем системную temp-директорию с уникальным именем
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"test_db_{os.getpid()}.db")
    
    # Удаляем файл, если он существует
    if os.path.exists(temp_path):
        os.unlink(temp_path)
    
    db = DBManager(temp_path)
    db.init_db()
    
    yield db
    
    db.close()
    
    # Удаляем тестовую БД после теста
    if os.path.exists(temp_path):
        os.unlink(temp_path)

def test_create_order(db):
    """Создание заказа работает"""
    order_id = db.add_order(
        user_id=12345,
        client_name="Тест",
        phone="+79991234567",
        service_id="service1",
        service_name="Стрижка",
        booking_date="2026-01-10",
        booking_time="14:00",
        price=1000
    )
    assert order_id is not None

def test_check_slot_availability_free(db):
    """Свободный слот доступен"""
    is_free = db.check_slot_availability("2026-01-10", "14:00")
    assert is_free == True

def test_check_slot_availability_taken(db):
    """Занятый слот недоступен"""
    db.add_order(
        user_id=12345,
        client_name="Тест",
        phone="+79991234567",
        service_id="service1",
        service_name="Стрижка",
        booking_date="2026-01-10",
        booking_time="14:00",
        price=1000
    )
    is_free = db.check_slot_availability("2026-01-10", "14:00")
    assert is_free == False

def test_get_user_orders(db):
    """Получение заказов пользователя работает"""
    db.add_order(1, "Client1", "+1", "s1", "Service1", "2026-01-10", "10:00", 100)
    db.add_order(1, "Client1", "+1", "s2", "Service2", "2026-01-11", "11:00", 200)
    db.add_order(2, "Client2", "+2", "s3", "Service3", "2026-01-12", "12:00", 300)
    
    orders = db.get_user_orders(1)
    assert len(orders) == 2
    assert orders[0]["service_name"] == "Service1"
    
    orders_user2 = db.get_user_orders(2)
    assert len(orders_user2) == 1
    
    orders_user3 = db.get_user_orders(3)
    assert len(orders_user3) == 0

def test_cancel_order(db):
    """Отмена заказа работает"""
    order_id = db.add_order(1, "Client1", "+1", "s1", "Service1", "2026-01-15", "15:00", 500)
    
    # Проверяем, что слот занят
    is_free_before = db.check_slot_availability("2026-01-15", "15:00")
    assert not is_free_before
    
    # Отменяем заказ
    db.cancel_order(order_id, 1)
    
    # Проверяем, что слот освободился
    is_free_after = db.check_slot_availability("2026-01-15", "15:00")
    assert is_free_after
    
    # Проверяем, что заказ нельзя отменить дважды или чужой заказ
    with pytest.raises(ValueError):
        db.cancel_order(order_id, 1) # Уже отменен
    
    order_id_2 = db.add_order(2, "Client2", "+2", "s2", "S2", "2026-01-16", "16:00", 600)
    with pytest.raises(ValueError):
        db.cancel_order(order_id_2, 1) # Чужой заказ

def test_get_upcoming_bookings(db):
    """Получение предстоящих записей работает"""
    db.add_order(1, "1", "1", "s1", "S1", "2024-01-01", "10:00", 100) # Прошедшая
    db.add_order(2, "2", "2", "s2", "S2", "2099-12-30", "11:00", 200) # Будущая
    db.add_order(3, "3", "3", "s3", "S3", "2099-12-31", "12:00", 300) # Будущая
    
    bookings = db.get_upcoming_bookings(limit=5)
    assert len(bookings) == 2
    assert bookings[0]["client_name"] == "2"
