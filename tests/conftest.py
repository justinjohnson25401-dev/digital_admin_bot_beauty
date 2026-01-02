import pytest
from datetime import datetime, date

@pytest.fixture
def sample_config():
    """Тестовая конфигурация бота"""
    return {
        "business_name": "Тестовый салон",
        "booking": {
            "work_start": 10,
            "work_end": 20,
            "slot_duration": 60
        },
        "staff": {
            "enabled": True,
            "masters": [
                {
                    "id": "master1",
                    "name": "Анна",
                    "active": True,
                    "services": ["service1"],
                    "closed_dates": [
                        {"date": "2026-01-05", "reason": "Выходной"}
                    ]
                }
            ]
        },
        "services": [
            {"id": "service1", "name": "Стрижка", "price": 1000, "duration": 60}
        ]
    }