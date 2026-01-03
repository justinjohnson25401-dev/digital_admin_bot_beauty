"""
Тесты для config_loader и config_editor.
"""

import pytest
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_loader import load_config
from utils.config_editor import ConfigEditor


class TestConfigLoader:
    """Тесты для config_loader."""

    @pytest.fixture
    def temp_config_dir(self):
        """Создать временную директорию с конфигом."""
        temp_dir = tempfile.mkdtemp()
        config_file = os.path.join(temp_dir, 'client_lite.json')

        test_config = {
            "bot_token": "TEST_TOKEN",
            "business_name": "Тест Салон",
            "admin_ids": [123456789],
            "services": [
                {"id": "s1", "name": "Стрижка", "price": 1000, "category": "Волосы"},
                {"id": "s2", "name": "Маникюр", "price": 1500, "category": "Ногти"}
            ],
            "staff": {
                "enabled": True,
                "masters": [
                    {"id": "m1", "name": "Анна", "services": ["s1"], "schedule": {}}
                ]
            },
            "booking": {"work_start": 10, "work_end": 20, "slot_duration": 60},
            "features": {"require_phone": True},
            "messages": {"welcome": "Добро пожаловать!"}
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, ensure_ascii=False)

        yield temp_dir

        os.remove(config_file)
        os.rmdir(temp_dir)

    def test_load_config_success(self, temp_config_dir):
        """Должен загружать конфиг."""
        config = load_config(temp_config_dir)
        assert config is not None
        assert config['business_name'] == 'Тест Салон'
        assert len(config['services']) == 2
        assert config['staff']['enabled'] is True

    def test_load_config_services(self, temp_config_dir):
        """Должен загружать услуги."""
        config = load_config(temp_config_dir)
        services = config['services']
        assert len(services) == 2
        assert services[0]['name'] == 'Стрижка'
        assert services[0]['price'] == 1000

    def test_load_config_staff(self, temp_config_dir):
        """Должен загружать персонал."""
        config = load_config(temp_config_dir)
        staff = config['staff']
        assert staff['enabled'] is True
        assert len(staff['masters']) == 1
        assert staff['masters'][0]['name'] == 'Анна'


class TestConfigEditor:
    """Тесты для ConfigEditor."""

    @pytest.fixture
    def editor_with_config(self):
        """Создать ConfigEditor с тестовым конфигом."""
        temp_dir = tempfile.mkdtemp()
        config_file = os.path.join(temp_dir, 'client_lite.json')

        test_config = {
            "services": [{"id": "s1", "name": "Услуга 1", "price": 100}],
            "staff": {"enabled": True, "masters": [{"id": "m1", "name": "Мастер 1", "services": ["s1"]}]}
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, ensure_ascii=False)

        # ConfigEditor expects path to file, not directory
        editor = ConfigEditor(config_file)

        yield editor, temp_dir, config_file

        if os.path.exists(config_file):
            os.remove(config_file)
        os.rmdir(temp_dir)

    def test_load_config(self, editor_with_config):
        """Должен загружать конфиг."""
        editor, _, _ = editor_with_config
        config = editor.load()
        assert config is not None
        assert 'services' in config
        assert 'staff' in config

    def test_add_service(self, editor_with_config):
        """Должен добавлять услугу."""
        editor, _, _ = editor_with_config
        new_service = {"name": "Новая услуга", "price": 500, "category": "Тест"}
        service_id = editor.add_service(new_service)
        assert service_id is not None
        config = editor.load()
        service_ids = [s['id'] for s in config['services']]
        assert service_id in service_ids

    def test_add_master(self, editor_with_config):
        """Должен добавлять мастера."""
        editor, _, _ = editor_with_config
        new_master = {"name": "Новый мастер", "role": "Стилист", "services": ["s1"], "schedule": {}}
        master_id = editor.add_master(new_master)
        assert master_id is not None
        config = editor.load()
        master_ids = [m['id'] for m in config['staff']['masters']]
        assert master_id in master_ids

    def test_delete_master(self, editor_with_config):
        """Должен удалять мастера."""
        editor, _, _ = editor_with_config
        result = editor.delete_master("m1")
        assert result is True
        config = editor.load()
        master_ids = [m['id'] for m in config['staff']['masters']]
        assert "m1" not in master_ids
