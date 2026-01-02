"""
Вспомогательные функции для процесса бронирования.
"""

from datetime import datetime

def get_categories_from_services(services: list) -> list:
    """Извлекает уникальные категории из списка услуг."""
    categories = []
    seen = set()
    for svc in services:
        cat = svc.get('category', 'Другое')
        if cat not in seen:
            seen.add(cat)
            categories.append(cat)
    return categories

def get_services_by_category(services: list, category: str) -> list:
    """Фильтрует услуги по заданной категории."""
    return [s for s in services if s.get('category', 'Другое') == category]

def get_masters_for_service(config: dict, service_id: str) -> list:
    """Возвращает список мастеров, оказывающих данную услугу."""
    staff = config.get('staff', {})
    if not staff.get('enabled', False):
        return []
    masters = staff.get('masters', [])
    return [m for m in masters if m.get('active', True) and (service_id in m.get('services', []) or not m.get('services', []))]

def get_master_by_id(config: dict, master_id: str) -> dict:
    """Находит мастера по его ID."""
    return next((m for m in config.get('staff', {}).get('masters', []) if m.get('id') == master_id), None)

def is_date_closed_for_master(config: dict, master_id: str, date_obj) -> tuple:
    """Проверяет, является ли дата закрытой для мастера."""
    if not master_id:
        return False, None
    master = get_master_by_id(config, master_id)
    if not master:
        return False, None
    date_str = date_obj.isoformat() if hasattr(date_obj, 'isoformat') else str(date_obj)
    for closed in master.get('closed_dates', []):
        if closed.get('date') == date_str:
            return True, closed.get('reason', '')
    return False, None

def format_booking_summary(data: dict) -> str:
    """Форматирует итоговую информацию о бронировании."""
    service_name = data.get('service_name', 'Услуга')
    price = data.get('price', 0)
    booking_date = data.get('booking_date', '')
    booking_time = data.get('booking_time', '')
    client_name = data.get('client_name', '')
    phone = data.get('phone', '')
    comment = data.get('comment', '')
    master_name = data.get('master_name')

    try:
        date_formatted = datetime.fromisoformat(booking_date).strftime('%d.%m.%Y')
    except Exception:
        date_formatted = booking_date

    text = (
        f"📋 <b>Подтверждение записи</b>\n\n"
        f"💇 Услуга: {service_name}\n"
        f"💰 Цена: {price}₽\n"
    )

    if master_name:
        text += f"👤 Мастер: {master_name}\n"

    text += (
        f"📅 Дата: {date_formatted}\n"
        f"🕐 Время: {booking_time}\n"
        f"👤 Имя: {client_name}\n"
        f"📞 Телефон: {phone}\n"
    )

    if comment:
        text += f"💬 Комментарий: {comment}\n"

    text += "\n✅ Всё верно?"
    return text
