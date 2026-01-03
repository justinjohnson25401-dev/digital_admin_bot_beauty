"""
Интеграционные тесты запуска ботов.
"""

import pytest
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestBotStartupIntegration:
    """Интеграционные тесты для проверки запуска ботов."""

    @pytest.fixture
    def mock_config_dir(self):
        """Создать директорию с тестовым конфигом."""
        temp_dir = tempfile.mkdtemp()
        config_file = os.path.join(temp_dir, 'client_lite.json')
        
        test_config = {
            "bot_token": "TEST_BOT_TOKEN",
            "admin_bot_token": "TEST_ADMIN_TOKEN",
            "business_name": "Тест Салон",
            "admin_ids": [123456789],
            "services": [
                {"id": "s1", "name": "Стрижка", "price": 1000, "category": "Волосы", "duration": 60}
            ],
            "staff": {
                "enabled": True,
                "masters": []
            },
            "booking": {
                "work_start": 10,
                "work_end": 20,
                "slot_duration": 60
            },
            "features": {
                "require_phone": True,
                "enable_slot_booking": True,
                "enable_admin_notify": True
            },
            "messages": {
                "welcome": "Добро пожаловать!",
                "success": "Запись создана!",
                "booking_cancelled": "Запись отменена."
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, ensure_ascii=False)
        
        yield temp_dir
        
        os.remove(config_file)
        os.rmdir(temp_dir)

    def test_config_loader_works(self, mock_config_dir):
        """Конфиг должен загружаться без ошибок."""
        from utils.config_loader import load_config
        
        config = load_config(mock_config_dir)
        
        assert config is not None
        assert config['business_name'] == 'Тест Салон'
        assert 'services' in config

    def test_database_manager_initializes(self, mock_config_dir):
        """DatabaseManager должен инициализироваться."""
        from utils.db import DatabaseManager

        os.environ['CONFIG_DIR'] = mock_config_dir
        db = DatabaseManager('integration_test')

        assert db is not None
        # Connection доступно через db.db.connection (внутренний Database объект)
        assert db.db.connection is not None

        db.close()

    def test_handlers_routers_exist(self):
        """Все роутеры должны существовать."""
        from handlers.booking import router as booking_router
        from handlers.mybookings import router as mybookings_router
        from handlers.start import router as start_router
        
        assert booking_router is not None
        assert mybookings_router is not None
        assert start_router is not None

    def test_admin_handlers_routers_exist(self):
        """Админ роутеры должны существовать."""
        from admin_handlers.staff import router as staff_router
        from admin_handlers import services_editor
        from admin_handlers import settings_editor
        
        assert staff_router is not None
        assert services_editor is not None
        assert settings_editor is not None

    def test_states_defined(self):
        """FSM состояния должны быть определены."""
        from states.booking import BookingState, EditBookingState
        from admin_bot.states import StaffEditorStates, ServiceEditorStates
        
        # Проверяем что это StatesGroup
        assert hasattr(BookingState, 'choosing_service')
        assert hasattr(EditBookingState, 'choosing_action')
        assert hasattr(StaffEditorStates, 'enter_name')

    def test_calendar_classes_exist(self):
        """Классы календаря должны существовать."""
        from utils.calendar import DialogCalendar, DialogCalendarCallback, generate_calendar_keyboard
        
        assert DialogCalendar is not None
        assert DialogCalendarCallback is not None
        assert generate_calendar_keyboard is not None

    def test_staff_manager_works(self, mock_config_dir):
        """StaffManager должен работать."""
        from utils.config_loader import load_config
        from utils.staff_manager import StaffManager
        
        config = load_config(mock_config_dir)
        manager = StaffManager(config)
        
        assert manager.is_enabled() is True
        assert manager.get_all_masters() == []
