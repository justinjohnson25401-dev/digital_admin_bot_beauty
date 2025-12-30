"""
FSM состояния для админ-панели.
Определяет все состояния для многошаговых диалогов.
"""

from aiogram.fsm.state import State, StatesGroup


class BusinessSettingsStates(StatesGroup):
    """Состояния для редактирования настроек бизнеса"""
    edit_name = State()
    edit_work_start = State()
    edit_work_end = State()
    edit_slot_duration = State()
    edit_timezone = State()


class ServiceEditorStates(StatesGroup):
    """Состояния для управления услугами"""
    # Добавление услуги
    enter_service_name = State()
    enter_price = State()
    enter_duration = State()
    choose_category = State()
    enter_new_category = State()
    confirm_add = State()

    # Редактирование услуги
    choose_service = State()
    choose_edit_field = State()
    edit_name = State()
    edit_price = State()
    edit_duration = State()
    edit_category = State()

    # Управление категориями
    manage_categories = State()
    enter_category_name = State()
    rename_category = State()
    confirm_delete_category = State()


class TextsEditorStates(StatesGroup):
    """Состояния для редактирования текстов"""
    choose_message = State()
    enter_text = State()
    confirm_text = State()

    # FAQ
    manage_faq = State()
    choose_faq_action = State()
    enter_button_text = State()
    enter_answer = State()
    choose_faq_item = State()
    edit_faq_field = State()
    confirm_delete_faq = State()


class NotificationsEditorStates(StatesGroup):
    """Состояния для настройки уведомлений"""
    main_menu = State()
    toggle_notification = State()


class StaffEditorStates(StatesGroup):
    """Состояния для управления персоналом"""
    # Главное меню
    choose_action = State()

    # Добавление мастера
    enter_name = State()
    enter_role = State()
    choose_services = State()
    choose_schedule_template = State()
    choose_schedule_days = State()  # Мультиселект дней недели
    choose_schedule_hours = State()  # Выбор времени работы
    confirm_add = State()

    # Ручная настройка графика
    manual_schedule_day = State()
    manual_schedule_start = State()
    manual_schedule_end = State()
    manual_schedule_confirm = State()

    # Редактирование мастера
    choose_master = State()
    choose_edit_field = State()
    edit_name = State()
    edit_role = State()
    edit_services = State()
    edit_schedule = State()

    # Управление графиком (закрытые даты)
    manage_schedule = State()
    choose_schedule_date = State()
    enter_close_reason = State()
    confirm_open_date = State()

    # Удаление
    confirm_delete = State()


class CategoryEditorStates(StatesGroup):
    """Состояния для управления категориями услуг"""
    list_categories = State()
    add_category = State()
    enter_new_name = State()
    choose_category_to_edit = State()
    edit_category_name = State()
    confirm_delete = State()


class FAQEditorStates(StatesGroup):
    """Состояния для управления FAQ"""
    list_faq = State()
    add_button_text = State()
    add_answer = State()
    choose_faq_to_edit = State()
    edit_button = State()
    edit_answer = State()
    confirm_delete = State()


class ClosedDatesStates(StatesGroup):
    """Состояния для управления закрытыми датами мастеров"""
    choose_master = State()
    show_dates = State()
    add_date = State()
    enter_date = State()
    enter_reason = State()
    confirm_remove = State()
