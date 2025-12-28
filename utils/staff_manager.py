"""
Менеджер персонала - работа с мастерами и графиками.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any


class StaffManager:
    """Управление персоналом и графиками"""

    # Названия дней недели на английском (для schedule)
    WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    # Русские названия дней
    WEEKDAYS_RU = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье'
    }

    # Короткие русские названия
    WEEKDAYS_SHORT_RU = {
        'monday': 'Пн',
        'tuesday': 'Вт',
        'wednesday': 'Ср',
        'thursday': 'Чт',
        'friday': 'Пт',
        'saturday': 'Сб',
        'sunday': 'Вс'
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.staff = config.get('staff', {})

    def reload(self, config: Dict[str, Any]) -> None:
        """Перезагрузить конфигурацию"""
        self.config = config
        self.staff = config.get('staff', {})

    def is_enabled(self) -> bool:
        """Включена ли функция персонала"""
        return self.staff.get('enabled', False)

    def get_all_masters(self) -> List[Dict]:
        """Получить всех мастеров"""
        return self.staff.get('masters', [])

    def get_masters_for_service(self, service_id: str) -> List[Dict]:
        """Получить мастеров, выполняющих услугу"""
        if not self.is_enabled():
            return []

        return [
            m for m in self.staff.get('masters', [])
            if service_id in m.get('services', [])
        ]

    def get_master_by_id(self, master_id: str) -> Optional[Dict]:
        """Получить мастера по ID"""
        for master in self.staff.get('masters', []):
            if master['id'] == master_id:
                return master
        return None

    def is_master_working(self, master: Dict, target_date: date) -> bool:
        """Работает ли мастер в эту дату"""
        return self.get_working_hours(master, target_date) is not None

    def get_working_hours(self, master: Dict, target_date: date) -> Optional[Dict[str, str]]:
        """
        Получить рабочие часы мастера на дату.

        Возвращает: {"start": "09:00", "end": "18:00"} или None
        """
        # Проверка на закрытую дату
        for closed in master.get('closed_dates', []):
            if closed.get('date') == target_date.isoformat():
                return None

        # Проверка графика
        day_name = self.WEEKDAYS[target_date.weekday()]
        schedule = master.get('schedule', {}).get(day_name, {})

        if not schedule.get('working', False):
            return None

        return {
            'start': schedule.get('start', '09:00'),
            'end': schedule.get('end', '18:00')
        }

    def get_available_slots(
        self,
        master: Dict,
        target_date: date,
        slot_duration: int,
        service_duration: int = None,
        occupied_slots: List[str] = None
    ) -> List[str]:
        """
        Получить свободные слоты для мастера.

        Параметры:
        - master: данные мастера
        - target_date: дата
        - slot_duration: длительность слота в минутах (из конфига бронирования)
        - service_duration: длительность услуги (для проверки, что влезет)
        - occupied_slots: список занятых слотов (опционально)

        Возвращает: список времён в формате "09:00", "09:30" и т.д.
        """
        hours = self.get_working_hours(master, target_date)
        if not hours:
            return []

        # Генерация всех возможных слотов
        start = datetime.strptime(hours['start'], '%H:%M').time()
        end = datetime.strptime(hours['end'], '%H:%M').time()

        slots = []
        current = datetime.combine(target_date, start)
        end_dt = datetime.combine(target_date, end)

        # Если указана длительность услуги, учитываем её
        effective_duration = service_duration if service_duration else slot_duration

        while current + timedelta(minutes=effective_duration) <= end_dt:
            slot_time = current.strftime('%H:%M')

            # Исключить занятые слоты
            if occupied_slots and slot_time in occupied_slots:
                current += timedelta(minutes=slot_duration)
                continue

            slots.append(slot_time)
            current += timedelta(minutes=slot_duration)

        return slots

    def get_available_dates(
        self,
        master: Dict,
        start_date: date,
        days_ahead: int = 30
    ) -> List[date]:
        """
        Получить дни, когда мастер работает.

        Параметры:
        - master: данные мастера
        - start_date: начальная дата
        - days_ahead: сколько дней вперёд смотреть (по умолчанию 30)

        Возвращает: список дат
        """
        available = []
        current = start_date

        for _ in range(days_ahead):
            if self.is_master_working(master, current):
                available.append(current)
            current += timedelta(days=1)

        return available

    def get_schedule_summary(self, master: Dict) -> str:
        """
        Получить краткое описание графика мастера.

        Возвращает: строку вида "Пн-Пт 9:00-18:00"
        """
        schedule = master.get('schedule', {})
        if not schedule:
            return "График не задан"

        # Группировка по одинаковым часам
        groups = {}
        for day in self.WEEKDAYS:
            day_schedule = schedule.get(day, {})
            if day_schedule.get('working', False):
                hours = f"{day_schedule.get('start', '09:00')}-{day_schedule.get('end', '18:00')}"
                if hours not in groups:
                    groups[hours] = []
                groups[hours].append(day)

        if not groups:
            return "Выходные"

        # Форматирование
        parts = []
        for hours, days in groups.items():
            days_str = self._format_days_range(days)
            parts.append(f"{days_str} {hours}")

        return ", ".join(parts)

    def _format_days_range(self, days: List[str]) -> str:
        """Форматировать список дней в диапазон (Пн-Пт)"""
        if not days:
            return ""

        if len(days) == 1:
            return self.WEEKDAYS_SHORT_RU[days[0]]

        # Проверка на последовательность
        indices = [self.WEEKDAYS.index(d) for d in days]
        indices.sort()

        is_consecutive = all(
            indices[i] + 1 == indices[i + 1]
            for i in range(len(indices) - 1)
        )

        if is_consecutive and len(days) > 2:
            first = self.WEEKDAYS_SHORT_RU[self.WEEKDAYS[indices[0]]]
            last = self.WEEKDAYS_SHORT_RU[self.WEEKDAYS[indices[-1]]]
            return f"{first}-{last}"
        else:
            return ", ".join(self.WEEKDAYS_SHORT_RU[d] for d in days)

    def format_closed_dates(self, master: Dict, limit: int = 5) -> str:
        """
        Форматировать закрытые даты для отображения.

        Параметры:
        - master: данные мастера
        - limit: максимальное количество дат для показа

        Возвращает: форматированную строку
        """
        closed_dates = master.get('closed_dates', [])

        if not closed_dates:
            return "Нет закрытых дат"

        # Фильтруем только будущие даты
        today = date.today()
        future_dates = [
            cd for cd in closed_dates
            if datetime.strptime(cd['date'], '%Y-%m-%d').date() >= today
        ]

        if not future_dates:
            return "Нет будущих закрытых дат"

        # Сортировка по дате
        future_dates.sort(key=lambda x: x['date'])

        lines = []
        for i, cd in enumerate(future_dates[:limit]):
            date_obj = datetime.strptime(cd['date'], '%Y-%m-%d').date()
            date_str = date_obj.strftime('%d.%m.%Y')
            reason = cd.get('reason', '')

            if reason:
                lines.append(f"• {date_str} — {reason}")
            else:
                lines.append(f"• {date_str}")

        if len(future_dates) > limit:
            lines.append(f"... и ещё {len(future_dates) - limit}")

        return "\n".join(lines)

    @staticmethod
    def create_default_schedule(template: str = "mon_fri_9_18") -> Dict[str, Dict]:
        """
        Создать график по шаблону.

        Шаблоны:
        - mon_fri_9_18: Пн-Пт 9:00-18:00
        - mon_fri_10_20: Пн-Пт 10:00-20:00
        - tue_sat_10_20: Вт-Сб 10:00-20:00
        - mon_sat_10_21: Пн-Сб 10:00-21:00
        - all_days_10_20: Все дни 10:00-20:00
        """
        templates = {
            "mon_fri_9_18": {
                "monday": {"working": True, "start": "09:00", "end": "18:00"},
                "tuesday": {"working": True, "start": "09:00", "end": "18:00"},
                "wednesday": {"working": True, "start": "09:00", "end": "18:00"},
                "thursday": {"working": True, "start": "09:00", "end": "18:00"},
                "friday": {"working": True, "start": "09:00", "end": "18:00"},
                "saturday": {"working": False},
                "sunday": {"working": False},
            },
            "mon_fri_10_20": {
                "monday": {"working": True, "start": "10:00", "end": "20:00"},
                "tuesday": {"working": True, "start": "10:00", "end": "20:00"},
                "wednesday": {"working": True, "start": "10:00", "end": "20:00"},
                "thursday": {"working": True, "start": "10:00", "end": "20:00"},
                "friday": {"working": True, "start": "10:00", "end": "20:00"},
                "saturday": {"working": False},
                "sunday": {"working": False},
            },
            "tue_sat_10_20": {
                "monday": {"working": False},
                "tuesday": {"working": True, "start": "10:00", "end": "20:00"},
                "wednesday": {"working": True, "start": "10:00", "end": "20:00"},
                "thursday": {"working": True, "start": "10:00", "end": "20:00"},
                "friday": {"working": True, "start": "10:00", "end": "20:00"},
                "saturday": {"working": True, "start": "10:00", "end": "20:00"},
                "sunday": {"working": False},
            },
            "mon_sat_10_21": {
                "monday": {"working": True, "start": "10:00", "end": "21:00"},
                "tuesday": {"working": True, "start": "10:00", "end": "21:00"},
                "wednesday": {"working": True, "start": "10:00", "end": "21:00"},
                "thursday": {"working": True, "start": "10:00", "end": "21:00"},
                "friday": {"working": True, "start": "10:00", "end": "21:00"},
                "saturday": {"working": True, "start": "10:00", "end": "21:00"},
                "sunday": {"working": False},
            },
            "all_days_10_20": {
                "monday": {"working": True, "start": "10:00", "end": "20:00"},
                "tuesday": {"working": True, "start": "10:00", "end": "20:00"},
                "wednesday": {"working": True, "start": "10:00", "end": "20:00"},
                "thursday": {"working": True, "start": "10:00", "end": "20:00"},
                "friday": {"working": True, "start": "10:00", "end": "20:00"},
                "saturday": {"working": True, "start": "10:00", "end": "20:00"},
                "sunday": {"working": True, "start": "10:00", "end": "20:00"},
            },
        }

        return templates.get(template, templates["mon_fri_9_18"])

    @staticmethod
    def get_schedule_templates() -> Dict[str, str]:
        """
        Получить словарь шаблонов графиков для отображения.

        Возвращает: {template_id: описание}
        """
        return {
            "mon_fri_9_18": "Пн-Пт 9:00-18:00",
            "mon_fri_10_20": "Пн-Пт 10:00-20:00",
            "tue_sat_10_20": "Вт-Сб 10:00-20:00",
            "mon_sat_10_21": "Пн-Сб 10:00-21:00",
            "all_days_10_20": "Все дни 10:00-20:00",
        }

    def get_master_services_names(self, master: Dict) -> List[str]:
        """
        Получить названия услуг мастера.

        Возвращает: список названий услуг
        """
        master_service_ids = master.get('services', [])
        all_services = self.config.get('services', [])

        names = []
        for service_id in master_service_ids:
            for service in all_services:
                if service['id'] == service_id:
                    names.append(service['name'])
                    break

        return names

    def format_master_info(self, master: Dict, include_schedule: bool = True) -> str:
        """
        Форматировать информацию о мастере для отображения.

        Параметры:
        - master: данные мастера
        - include_schedule: включить график

        Возвращает: форматированную строку
        """
        lines = [
            f"👤 {master['name']}",
            f"💼 {master.get('specialization') or master.get('role', 'Мастер')}",
        ]

        # Услуги
        services = self.get_master_services_names(master)
        if services:
            services_str = ", ".join(services[:3])
            if len(services) > 3:
                services_str += f" (+{len(services) - 3})"
            lines.append(f"📋 Услуги: {services_str}")

        # График
        if include_schedule:
            schedule_str = self.get_schedule_summary(master)
            lines.append(f"📅 График: {schedule_str}")

        # Закрытые даты
        closed_dates = master.get('closed_dates', [])
        future_closed = [
            cd for cd in closed_dates
            if datetime.strptime(cd['date'], '%Y-%m-%d').date() >= date.today()
        ]
        if future_closed:
            lines.append(f"🚫 Закрытых дат: {len(future_closed)}")

        return "\n".join(lines)
