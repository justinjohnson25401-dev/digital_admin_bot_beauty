"""
Вспомогательные функции для процесса бронирования.
"""

def get_categories_from_services(services: list) -> list:
    """Extracts unique categories from a list of services."""
    categories = []
    for service in services:
        if service.get('category') and service['category'] not in categories:
            categories.append(service['category'])
    return categories

def get_services_by_category(services: list, category_name: str) -> list:
    """Filters services by a given category name."""
    return [s for s in services if s.get('category') == category_name]

def get_masters_for_service(config: dict, service_id: str) -> list:
    """Gets a list of masters who provide a specific service."""
    staff_list = config.get('staff', {}).get('list', [])
    return [master for master in staff_list if service_id in master.get('services', [])]

def get_master_by_id(config: dict, master_id: str) -> dict or None:
    """Finds a master by their ID."""
    return next((m for m in config.get('staff', {}).get('list', []) if m['id'] == master_id), None)
