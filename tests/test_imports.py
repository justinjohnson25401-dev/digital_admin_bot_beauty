"""
Проверка всех импортов в проекте.
Этот тест должен найти ВСЕ сломанные импорты.
"""

import pytest
import sys
import os
import importlib
import ast

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestImports:
    """Тесты импортов всех модулей проекта."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Установка корневой директории проекта."""
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_utils_db_import(self):
        """Тест импорта utils.db"""
        import utils.db
        from utils.db import DatabaseManager
        assert DatabaseManager is not None

    def test_utils_config_loader_import(self):
        """Тест импорта utils.config_loader"""
        import utils.config_loader
        from utils.config_loader import load_config
        assert load_config is not None

    def test_utils_config_editor_import(self):
        """Тест импорта utils.config_editor"""
        import utils.config_editor
        from utils.config_editor import ConfigEditor
        assert ConfigEditor is not None

    def test_utils_logger_import(self):
        """Тест импорта utils.logger"""
        import utils.logger
        from utils.logger import setup_logger
        assert setup_logger is not None

    def test_utils_calendar_import(self):
        """Тест импорта utils.calendar"""
        import utils.calendar
        from utils.calendar import generate_calendar_keyboard, DialogCalendar, DialogCalendarCallback
        assert generate_calendar_keyboard is not None
        assert DialogCalendar is not None
        assert DialogCalendarCallback is not None

    def test_utils_staff_manager_import(self):
        """Тест импорта utils.staff_manager"""
        import utils.staff_manager
        from utils.staff_manager import StaffManager
        assert StaffManager is not None

    def test_utils_validators_import(self):
        """Тест импорта utils.validators"""
        import utils.validators
        from utils.validators import is_valid_phone, clean_phone
        assert is_valid_phone is not None
        assert clean_phone is not None

    def test_utils_notify_import(self):
        """Тест импорта utils.notify"""
        import utils.notify
        from utils.notify import send_order_to_admins
        assert send_order_to_admins is not None

    def test_states_booking_import(self):
        """Тест импорта states.booking"""
        import states.booking
        from states.booking import BookingState, EditBookingState
        assert BookingState is not None
        assert EditBookingState is not None

    def test_admin_bot_states_import(self):
        """Тест импорта admin_bot.states"""
        import admin_bot.states
        from admin_bot.states import StaffEditorStates
        assert StaffEditorStates is not None

    def test_handlers_booking_import(self):
        """Тест импорта handlers.booking"""
        import handlers.booking
        assert handlers.booking.router is not None

    def test_handlers_start_import(self):
        """Тест импорта handlers.start"""
        import handlers.start
        assert handlers.start.router is not None

    def test_handlers_mybookings_import(self):
        """Тест импорта handlers.mybookings"""
        import handlers.mybookings
        assert handlers.mybookings.router is not None

    def test_admin_handlers_staff_import(self):
        """Тест импорта admin_handlers.staff"""
        import admin_handlers.staff
        assert admin_handlers.staff.router is not None

    def test_admin_bot_middleware_import(self):
        """Тест импорта admin_bot.middleware"""
        import admin_bot.middleware
        from admin_bot.middleware import ConfigMiddleware
        assert ConfigMiddleware is not None


class TestAllPythonFiles:
    """Тест на возможность импорта всех Python файлов."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Установка корневой директории проекта."""
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.exclude_dirs = {'__pycache__', '.git', 'venv', '.venv', 'tests'}

    def get_all_python_files(self):
        """Получить все Python файлы проекта."""
        python_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Исключаем ненужные директории
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for f in files:
                if f.endswith('.py') and not f.startswith('test_'):
                    filepath = os.path.join(root, f)
                    python_files.append(filepath)
        return python_files

    def test_all_files_have_valid_syntax(self):
        """Все Python файлы должны иметь корректный синтаксис."""
        files = self.get_all_python_files()
        errors = []

        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                ast.parse(content, filepath)
            except SyntaxError as e:
                errors.append(f"{filepath}: {e}")

        assert not errors, f"Syntax errors found:\n" + "\n".join(errors)

    def test_no_broken_imports_in_files(self):
        """Проверка на отсутствие явно сломанных импортов."""
        files = self.get_all_python_files()

        # Известные неправильные импорты которых НЕ должно быть
        forbidden_imports = [
            'from utils.config_manager import',  # Должен быть config_editor
            'from utils.db import DBManager',    # Должен быть DatabaseManager
            'from logger import',                # Должен быть from utils.logger
        ]

        issues = []
        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for bad_import in forbidden_imports:
                        if bad_import in content:
                            issues.append(f"{filepath}: contains '{bad_import}'")
            except Exception as e:
                issues.append(f"{filepath}: Error reading file: {e}")

        assert not issues, f"Forbidden imports found:\n" + "\n".join(issues)


class TestModuleStructure:
    """Тесты структуры модулей."""

    def test_handlers_booking_has_router(self):
        """handlers.booking должен экспортировать router."""
        from handlers.booking import router
        assert router is not None

    def test_handlers_mybookings_has_router(self):
        """handlers.mybookings должен экспортировать router."""
        from handlers.mybookings import router
        assert router is not None

    def test_admin_handlers_staff_has_router(self):
        """admin_handlers.staff должен экспортировать router."""
        from admin_handlers.staff import router
        assert router is not None

    def test_booking_utils_has_required_functions(self):
        """handlers.booking.utils должен содержать нужные функции."""
        from handlers.booking.utils import (
            get_categories_from_services,
            get_services_by_category,
            get_masters_for_service,
            get_master_by_id,
            is_date_closed_for_master,
            format_booking_summary,
        )
        assert all([
            get_categories_from_services,
            get_services_by_category,
            get_masters_for_service,
            get_master_by_id,
            is_date_closed_for_master,
            format_booking_summary,
        ])
