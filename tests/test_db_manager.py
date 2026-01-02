import pytest
import tempfile
import os
from utils.db_manager import DBManager

@pytest.fixture
def db():
    """Создаём временную БД для тестов"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db = DBManager(temp_file.name)
    db.init_db()
    
    yield db
    
    db.close()
    os.unlink(temp_file.name)

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