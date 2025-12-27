"""Менеджер конфигурации - сохранение и загрузка JSON"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ConfigManager:
    """Класс для управления конфигурацией"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise
    
    def save_config(self) -> bool:
        """Сохранение конфигурации в JSON"""
        try:
            current_version = self.config.get('config_version')
            try:
                current_version_int = int(current_version) if current_version is not None else 0
            except Exception:
                current_version_int = 0
            self.config['config_version'] = current_version_int + 1

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"Config saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False
    
    def update_service(self, service_id: str, **kwargs) -> bool:
        """Обновление услуги"""
        services = self.config.get('services', [])
        
        for service in services:
            if service['id'] == service_id:
                service.update(kwargs)
                return self.save_config()
        
        return False
    
    def add_service(self, name: str, price: int, duration: int = 60) -> bool:
        """Добавление новой услуги"""
        services = self.config.get('services', [])
        
        # Генерируем ID
        service_id = f"service{len(services) + 1}"
        
        new_service = {
            "id": service_id,
            "name": name,
            "price": price,
            "duration": duration
        }
        
        services.append(new_service)
        self.config['services'] = services
        
        return self.save_config()
    
    def delete_service(self, service_id: str) -> bool:
        """Удаление услуги"""
        services = self.config.get('services', [])
        
        self.config['services'] = [s for s in services if s['id'] != service_id]
        
        return self.save_config()
    
    def update_business_name(self, new_name: str) -> bool:
        """Обновление названия бизнеса"""
        self.config['business_name'] = new_name
        return self.save_config()
    
    def update_work_hours(self, start_hour: int, end_hour: int) -> bool:
        """Обновление графика работы"""
        if 'booking' not in self.config:
            self.config['booking'] = {}
        
        self.config['booking']['work_start'] = start_hour
        self.config['booking']['work_end'] = end_hour
        
        return self.save_config()
    
    def update_slot_duration(self, duration: int) -> bool:
        """Обновление длительности слота"""
        if 'booking' not in self.config:
            self.config['booking'] = {}
        
        self.config['booking']['slot_duration'] = duration
        
        return self.save_config()

    def update_timezone(self, city: str, offset_hours: int) -> bool:
        """Обновление таймзоны бизнеса (город + UTC offset в часах)"""
        self.config['timezone_city'] = city
        self.config['timezone_offset_hours'] = int(offset_hours)
        return self.save_config()

    def update_timezone_offset(self, offset_hours: int) -> bool:
        """Обновление только UTC offset в часах"""
        self.config['timezone_offset_hours'] = int(offset_hours)
        return self.save_config()

    def update_admin_pin_hash(self, pin_hash: str) -> bool:
        """Установка/смена PIN (хранится как sha256 в поле admin_pin_hash)"""
        self.config['admin_pin_hash'] = str(pin_hash)
        return self.save_config()

    def clear_admin_pin(self) -> bool:
        """Отключение PIN (удаляет поле admin_pin_hash)"""
        if 'admin_pin_hash' in self.config:
            del self.config['admin_pin_hash']
        return self.save_config()
    
    def get_config(self) -> Dict[str, Any]:
        """Получение текущей конфигурации"""
        return self.config
    
    def reload_config(self) -> Dict[str, Any]:
        """Перезагрузка конфигурации из файла"""
        self.config = self.load_config()
        return self.config
