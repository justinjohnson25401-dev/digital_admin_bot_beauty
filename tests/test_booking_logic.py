import pytest
from datetime import date, datetime, timedelta
from handlers.booking.utils import (
    is_date_closed_for_master,
    get_master_by_id,
    get_masters_for_service
)

def test_is_date_closed_returns_false_without_master(sample_config):
    """Если мастер не указан, дата не закрыта"""
    result, reason = is_date_closed_for_master(sample_config, None, date(2026, 1, 5))
    assert result == False

def test_is_date_closed_returns_true_for_closed_date(sample_config):
    """Если дата в списке закрытых, возвращает True"""
    result, reason = is_date_closed_for_master(sample_config, "master1", date(2026, 1, 5))
    assert result == True
    assert reason == "Выходной"

def test_is_date_open_returns_false(sample_config):
    """Если дата не в списке закрытых, возвращает False"""
    result, reason = is_date_closed_for_master(sample_config, "master1", date(2026, 1, 10))
    assert result == False

def test_get_master_by_id_found(sample_config):
    """Поиск мастера по ID работает"""
    master = get_master_by_id(sample_config, "master1")
    assert master is not None
    assert master["name"] == "Анна"

def test_get_master_by_id_not_found(sample_config):
    """Несуществующий ID возвращает None"""
    master = get_master_by_id(sample_config, "nonexistent")
    assert master is None

def test_get_masters_for_service(sample_config):
    """Получение списка мастеров для услуги"""
    masters = get_masters_for_service(sample_config, "service1")
    assert len(masters) == 1
    assert masters[0]["name"] == "Анна"