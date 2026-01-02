import pytest
import os
from utils.db_manager import DBManager

@pytest.fixture
def db(tmp_path):
    """Создаём временную БД для тестов"""
    # DBManager ожидает business_slug, а не полный путь
    # Он сам формирует путь как db_{slug}.sqlite
    
    # Переходим в tmp_path, чтобы БД создалась там
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Передаём только slug, DBManager сам добавит префикс db_ и .sqlite
        db = DBManager("test")
        db.init_db()
        
        yield db
        
        db.close()
    finally:
        # Возвращаемся в оригинальную директорию
        os.chdir(original_dir)

def test_create_order(db):
    """Создание заказа работает"""
    order_id = db.add_order(
        user_id=12345,
        service_id="service1",
        service_name="Стрижка",
        price=1000,
        client_name="Тест",
        phone="+79991234567",
        booking_date="2026-01-10",
        booking_time="14:00"
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
        service_id="service1",
        service_name="Стрижка",
        price=1000,
        client_name="Тест",
        phone="+79991234567",
        booking_date="2026-01-10",
        booking_time="14:00"
    )
    is_free = db.check_slot_availability("2026-01-10", "14:00")
    assert is_free == False

def test_get_user_orders(db):
    """Получение заказов пользователя работает"""
    db.add_order(1, "s1", "Service1", 100, "Client1", "+1", None, "2026-01-10", "10:00")
    db.add_order(1, "s2", "Service2", 200, "Client1", "+1", None, "2026-01-11", "11:00")
    db.add_order(2, "s3", "Service3", 300, "Client2", "+2", None, "2026-01-12", "12:00")
    orders = db.get_user_bookings(1)
    assert len(orders) == 2

def test_cancel_order(db):
    """Отмена заказа работает"""
    order_id = db.add_order(1, "s1", "Service1", 500, "Client1", "+1", None, "2026-01-15", "15:00")
    is_free_before = db.check_slot_availability("2026-01-15", "15:00")
    assert not is_free_before
    success = db.cancel_order(order_id)
    assert success

def test_get_upcoming_bookings(db):
    """Получение предстоящих записей работает"""
    db.add_order(1, "s1", "S1", 100, "1", "1", None, "2024-01-01", "10:00")
    db.add_order(2, "s2", "S2", 200, "2", "2", None, "2099-12-30", "11:00")
    db.add_order(3, "s3", "S3", 300, "3", "3", None, "2099-12-31", "12:00")
    bookings = db.get_active_orders_for_reminders()
    assert len(bookings) == 2


def test_race_condition_double_booking(db):
    """
    Тест на race condition: попытка забронировать уже занятый слот.
    add_order должен выбросить ValueError при попытке дублирования.
    """
    # Первое бронирование успешно
    order_id = db.add_order(
        user_id=1,
        service_id="s1",
        service_name="Service1",
        price=100,
        client_name="Client1",
        phone="+79991111111",
        comment=None,
        booking_date="2026-02-15",
        booking_time="14:00"
    )
    assert order_id is not None

    # Вторая попытка забронировать тот же слот должна провалиться
    try:
        db.add_order(
            user_id=2,
            service_id="s2",
            service_name="Service2",
            price=200,
            client_name="Client2",
            phone="+79992222222",
            comment=None,
            booking_date="2026-02-15",
            booking_time="14:00"
        )
        assert False, "Должен был выброситься ValueError"
    except ValueError as e:
        assert "занят" in str(e).lower() or "already" in str(e).lower()


def test_race_condition_same_master(db):
    """
    Тест на race condition для конкретного мастера.
    """
    # Первое бронирование для мастера master1
    order_id = db.add_order(
        user_id=1,
        service_id="s1",
        service_name="Service1",
        price=100,
        client_name="Client1",
        phone="+79991111111",
        comment=None,
        booking_date="2026-02-20",
        booking_time="10:00",
        master_id="master1"
    )
    assert order_id is not None

    # Попытка забронировать тот же слот у того же мастера
    try:
        db.add_order(
            user_id=2,
            service_id="s2",
            service_name="Service2",
            price=200,
            client_name="Client2",
            phone="+79992222222",
            comment=None,
            booking_date="2026-02-20",
            booking_time="10:00",
            master_id="master1"
        )
        assert False, "Должен был выброситься ValueError"
    except ValueError:
        pass  # Ожидаемое поведение


def test_different_masters_same_slot(db):
    """
    Разные мастера могут иметь записи на одно время.
    """
    # Бронирование для master1
    order1 = db.add_order(
        user_id=1,
        service_id="s1",
        service_name="Service1",
        price=100,
        client_name="Client1",
        phone="+79991111111",
        comment=None,
        booking_date="2026-02-25",
        booking_time="12:00",
        master_id="master1"
    )

    # Бронирование для master2 на то же время - должно пройти
    order2 = db.add_order(
        user_id=2,
        service_id="s2",
        service_name="Service2",
        price=200,
        client_name="Client2",
        phone="+79992222222",
        comment=None,
        booking_date="2026-02-25",
        booking_time="12:00",
        master_id="master2"
    )

    assert order1 is not None
    assert order2 is not None
    assert order1 != order2
