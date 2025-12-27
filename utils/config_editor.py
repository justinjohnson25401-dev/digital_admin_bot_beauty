"""
Расширенный редактор конфигурации для админ-панели.
Поддерживает работу с персоналом, категориями услуг, FAQ и сообщениями.
"""

import json
import re
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


class ConfigEditor:
    """Расширенный класс для управления файлом configs/client_lite.json"""

    def __init__(self, config_path: str = "configs/client_lite.json"):
        self.config_path = Path(config_path)

    def load(self) -> Dict[str, Any]:
        """Загрузить конфиг из JSON файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config: {e}")
            raise

    def save(self, config: Dict[str, Any]) -> None:
        """Сохранить конфиг в JSON файл с инкрементом версии"""
        # Инкремент версии
        current_version = config.get('config_version', 0)
        try:
            current_version = int(current_version)
        except (ValueError, TypeError):
            current_version = 0
        config['config_version'] = current_version + 1

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logger.info(f"Config saved (version {config['config_version']})")

    def update_field(self, path: str, value: Any) -> None:
        """
        Обновить поле по пути (поддерживает вложенные поля).

        Примеры:
        - update_field("business_name", "Новое имя")
        - update_field("booking.work_start", 9)
        - update_field("features.require_phone", True)
        """
        config = self.load()
        keys = path.split('.')
        current = config

        # Навигация к нужной ячейке
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Обновление значения
        current[keys[-1]] = value
        self.save(config)

    def get_field(self, path: str, default: Any = None) -> Any:
        """
        Получить значение поля по пути.

        Примеры:
        - get_field("business_name")
        - get_field("booking.work_start", 10)
        """
        config = self.load()
        keys = path.split('.')
        current = config

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    # ==================== УПРАВЛЕНИЕ УСЛУГАМИ ====================

    def add_service(self, service: Dict[str, Any]) -> str:
        """
        Добавить новую услугу.

        Параметры service:
        {
          "name": "Название услуги",
          "price": 1500,
          "duration": 60,
          "category": "Категория"  # опционально
        }

        Возвращает: service_id
        """
        config = self.load()

        # Генерация уникального ID
        service_id = self._generate_service_id(service['name'])
        service['id'] = service_id

        if 'services' not in config:
            config['services'] = []

        config['services'].append(service)
        self.save(config)

        logger.info(f"Service added: {service_id} - {service['name']}")
        return service_id

    def update_service(self, service_id: str, updates: Dict[str, Any]) -> bool:
        """
        Обновить услугу по ID.

        Возвращает: True если обновлено, False если услуга не найдена
        """
        config = self.load()

        for service in config.get('services', []):
            if service['id'] == service_id:
                # Не позволяем менять ID
                updates.pop('id', None)
                service.update(updates)
                self.save(config)
                logger.info(f"Service updated: {service_id}")
                return True

        logger.warning(f"Service not found: {service_id}")
        return False

    def delete_service(self, service_id: str) -> bool:
        """Удалить услугу по ID"""
        config = self.load()
        original_count = len(config.get('services', []))

        config['services'] = [
            s for s in config.get('services', [])
            if s['id'] != service_id
        ]

        if len(config['services']) < original_count:
            self.save(config)
            logger.info(f"Service deleted: {service_id}")
            return True

        logger.warning(f"Service not found for deletion: {service_id}")
        return False

    def get_service_by_id(self, service_id: str) -> Optional[Dict]:
        """Получить услугу по ID"""
        config = self.load()
        for service in config.get('services', []):
            if service['id'] == service_id:
                return service
        return None

    def get_all_services(self) -> List[Dict]:
        """Получить все услуги"""
        config = self.load()
        return config.get('services', [])

    # ==================== УПРАВЛЕНИЕ КАТЕГОРИЯМИ ====================

    def get_categories(self) -> List[str]:
        """Получить список всех категорий услуг"""
        config = self.load()
        categories = set()

        for service in config.get('services', []):
            if 'category' in service and service['category']:
                categories.add(service['category'])

        return sorted(list(categories))

    def get_services_by_category(self, category: str) -> List[Dict]:
        """Получить все услуги в категории"""
        config = self.load()
        return [
            s for s in config.get('services', [])
            if s.get('category') == category
        ]

    def rename_category(self, old_name: str, new_name: str) -> int:
        """
        Переименовать категорию для всех услуг.

        Возвращает: количество обновлённых услуг
        """
        config = self.load()
        count = 0

        for service in config.get('services', []):
            if service.get('category') == old_name:
                service['category'] = new_name
                count += 1

        if count > 0:
            self.save(config)
            logger.info(f"Category renamed: {old_name} -> {new_name} ({count} services)")

        return count

    def delete_category(self, category_name: str) -> int:
        """
        Удалить категорию (убрать поле category у услуг).

        Возвращает: количество обновлённых услуг
        """
        config = self.load()
        count = 0

        for service in config.get('services', []):
            if service.get('category') == category_name:
                del service['category']
                count += 1

        if count > 0:
            self.save(config)
            logger.info(f"Category deleted: {category_name} ({count} services)")

        return count

    # ==================== УПРАВЛЕНИЕ ПЕРСОНАЛОМ ====================

    def toggle_staff_feature(self, enabled: bool) -> None:
        """Включить/выключить функцию персонала"""
        config = self.load()

        if 'staff' not in config:
            config['staff'] = {'enabled': False, 'masters': []}

        config['staff']['enabled'] = enabled
        self.save(config)
        logger.info(f"Staff feature {'enabled' if enabled else 'disabled'}")

    def is_staff_enabled(self) -> bool:
        """Проверить, включена ли функция персонала"""
        config = self.load()
        return config.get('staff', {}).get('enabled', False)

    def add_master(self, master_data: Dict[str, Any]) -> str:
        """
        Добавить мастера.

        Параметры master_data:
        {
          "name": "Имя",
          "role": "Должность",
          "photo_url": null,  # опционально
          "services": ["service_id_1", "service_id_2"],
          "schedule": { "monday": {...}, ... }
        }

        Возвращает: master_id
        """
        config = self.load()

        if 'staff' not in config:
            config['staff'] = {'enabled': False, 'masters': []}

        # Генерация уникального ID
        master_id = f"master_{int(time.time())}"
        master_data['id'] = master_id
        master_data['closed_dates'] = master_data.get('closed_dates', [])
        master_data['photo_url'] = master_data.get('photo_url', None)

        config['staff']['masters'].append(master_data)
        self.save(config)

        logger.info(f"Master added: {master_id} - {master_data['name']}")
        return master_id

    def update_master(self, master_id: str, updates: Dict[str, Any]) -> bool:
        """Обновить данные мастера"""
        config = self.load()

        for master in config.get('staff', {}).get('masters', []):
            if master['id'] == master_id:
                # Не позволяем менять ID
                updates.pop('id', None)
                master.update(updates)
                self.save(config)
                logger.info(f"Master updated: {master_id}")
                return True

        logger.warning(f"Master not found: {master_id}")
        return False

    def delete_master(self, master_id: str) -> bool:
        """Удалить мастера"""
        config = self.load()

        if 'staff' not in config or 'masters' not in config['staff']:
            return False

        original_count = len(config['staff']['masters'])

        config['staff']['masters'] = [
            m for m in config['staff']['masters']
            if m['id'] != master_id
        ]

        if len(config['staff']['masters']) < original_count:
            self.save(config)
            logger.info(f"Master deleted: {master_id}")
            return True

        logger.warning(f"Master not found for deletion: {master_id}")
        return False

    def get_master_by_id(self, master_id: str) -> Optional[Dict]:
        """Получить мастера по ID"""
        config = self.load()
        for master in config.get('staff', {}).get('masters', []):
            if master['id'] == master_id:
                return master
        return None

    def get_all_masters(self) -> List[Dict]:
        """Получить всех мастеров"""
        config = self.load()
        return config.get('staff', {}).get('masters', [])

    def add_closed_date(self, master_id: str, date_str: str, reason: str = "") -> bool:
        """
        Закрыть дату для мастера (отпуск/больничный).

        Параметры:
        - master_id: ID мастера
        - date_str: дата в формате "YYYY-MM-DD"
        - reason: причина закрытия
        """
        config = self.load()

        for master in config.get('staff', {}).get('masters', []):
            if master['id'] == master_id:
                if 'closed_dates' not in master:
                    master['closed_dates'] = []

                # Проверка на дубликат
                for closed in master['closed_dates']:
                    if closed['date'] == date_str:
                        return False  # Уже закрыта

                master['closed_dates'].append({
                    'date': date_str,
                    'reason': reason
                })

                self.save(config)
                logger.info(f"Closed date added for {master_id}: {date_str}")
                return True

        return False

    def remove_closed_date(self, master_id: str, date_str: str) -> bool:
        """Открыть закрытую дату"""
        config = self.load()

        for master in config.get('staff', {}).get('masters', []):
            if master['id'] == master_id:
                original_count = len(master.get('closed_dates', []))
                master['closed_dates'] = [
                    d for d in master.get('closed_dates', [])
                    if d['date'] != date_str
                ]

                if len(master['closed_dates']) < original_count:
                    self.save(config)
                    logger.info(f"Closed date removed for {master_id}: {date_str}")
                    return True

        return False

    def get_closed_dates(self, master_id: str) -> List[Dict]:
        """Получить все закрытые даты мастера"""
        master = self.get_master_by_id(master_id)
        if master:
            return master.get('closed_dates', [])
        return []

    # ==================== УПРАВЛЕНИЕ FAQ ====================

    def get_faq(self) -> List[Dict]:
        """Получить все FAQ"""
        config = self.load()
        return config.get('faq', [])

    def add_faq(self, button_text: str, answer: str) -> bool:
        """Добавить новый FAQ"""
        config = self.load()

        if 'faq' not in config:
            config['faq'] = []

        config['faq'].append({
            'btn': button_text,
            'answer': answer
        })

        self.save(config)
        logger.info(f"FAQ added: {button_text}")
        return True

    def update_faq(self, index: int, button_text: str = None, answer: str = None) -> bool:
        """Обновить FAQ по индексу"""
        config = self.load()
        faq = config.get('faq', [])

        if 0 <= index < len(faq):
            if button_text is not None:
                faq[index]['btn'] = button_text
            if answer is not None:
                faq[index]['answer'] = answer
            self.save(config)
            logger.info(f"FAQ updated at index {index}")
            return True

        return False

    def delete_faq(self, index: int) -> bool:
        """Удалить FAQ по индексу"""
        config = self.load()
        faq = config.get('faq', [])

        if 0 <= index < len(faq):
            deleted = faq.pop(index)
            self.save(config)
            logger.info(f"FAQ deleted: {deleted['btn']}")
            return True

        return False

    def reorder_faq(self, old_index: int, new_index: int) -> bool:
        """Переместить FAQ на новую позицию"""
        config = self.load()
        faq = config.get('faq', [])

        if 0 <= old_index < len(faq) and 0 <= new_index < len(faq):
            item = faq.pop(old_index)
            faq.insert(new_index, item)
            self.save(config)
            return True

        return False

    # ==================== УПРАВЛЕНИЕ СООБЩЕНИЯМИ ====================

    def get_messages(self) -> Dict[str, str]:
        """Получить все сообщения"""
        config = self.load()
        return config.get('messages', {})

    def update_message(self, key: str, text: str) -> bool:
        """
        Обновить текст сообщения.

        Ключи: welcome, success, booking_cancelled, error_phone, error_generic, slot_taken
        """
        config = self.load()

        if 'messages' not in config:
            config['messages'] = {}

        config['messages'][key] = text
        self.save(config)
        logger.info(f"Message updated: {key}")
        return True

    def get_message(self, key: str, default: str = "") -> str:
        """Получить текст сообщения по ключу"""
        config = self.load()
        return config.get('messages', {}).get(key, default)

    # ==================== УПРАВЛЕНИЕ FEATURES ====================

    def get_features(self) -> Dict[str, bool]:
        """Получить все feature flags"""
        config = self.load()
        return config.get('features', {})

    def toggle_feature(self, feature_key: str) -> bool:
        """
        Переключить feature flag.

        Ключи: enable_slot_booking, enable_admin_notify, require_phone, ask_comment

        Возвращает: новое значение
        """
        config = self.load()

        if 'features' not in config:
            config['features'] = {}

        current_value = config['features'].get(feature_key, True)
        config['features'][feature_key] = not current_value

        self.save(config)
        logger.info(f"Feature toggled: {feature_key} = {not current_value}")
        return not current_value

    def set_feature(self, feature_key: str, value: bool) -> None:
        """Установить значение feature flag"""
        config = self.load()

        if 'features' not in config:
            config['features'] = {}

        config['features'][feature_key] = value
        self.save(config)

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def _generate_service_id(self, name: str) -> str:
        """Генерировать ID услуги из названия"""
        # Транслитерация кириллицы
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }

        name_lower = name.lower()
        transliterated = ''

        for char in name_lower:
            if char in translit_map:
                transliterated += translit_map[char]
            elif char.isalnum():
                transliterated += char
            else:
                transliterated += '_'

        # Убираем множественные подчёркивания
        slug = re.sub(r'_+', '_', transliterated).strip('_')

        # Обрезаем до 30 символов и добавляем время для уникальности
        slug = slug[:30]
        timestamp = int(time.time()) % 10000

        return f"{slug}_{timestamp}"

    def validate_config(self) -> tuple[bool, List[str]]:
        """
        Валидация конфигурации.

        Возвращает: (is_valid, list_of_errors)
        """
        errors = []

        try:
            config = self.load()
        except Exception as e:
            return False, [f"Cannot load config: {e}"]

        # Проверка обязательных полей
        required_fields = ['business_name', 'services', 'booking']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Проверка booking
        booking = config.get('booking', {})
        if 'work_start' not in booking:
            errors.append("Missing booking.work_start")
        if 'work_end' not in booking:
            errors.append("Missing booking.work_end")
        if booking.get('work_start', 0) >= booking.get('work_end', 24):
            errors.append("work_start must be less than work_end")

        # Проверка услуг
        services = config.get('services', [])
        if not services:
            errors.append("No services defined")

        for i, service in enumerate(services):
            if 'id' not in service:
                errors.append(f"Service {i}: missing 'id'")
            if 'name' not in service:
                errors.append(f"Service {i}: missing 'name'")
            if 'price' not in service:
                errors.append(f"Service {i}: missing 'price'")

        # Проверка персонала (если включён)
        staff = config.get('staff', {})
        if staff.get('enabled', False):
            masters = staff.get('masters', [])
            for i, master in enumerate(masters):
                if 'id' not in master:
                    errors.append(f"Master {i}: missing 'id'")
                if 'name' not in master:
                    errors.append(f"Master {i}: missing 'name'")
                if 'schedule' not in master:
                    errors.append(f"Master {i}: missing 'schedule'")

        return len(errors) == 0, errors
