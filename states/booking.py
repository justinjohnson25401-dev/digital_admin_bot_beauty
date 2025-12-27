from aiogram.fsm.state import State, StatesGroup


class BookingState(StatesGroup):
    """Состояния для процесса создания записи"""
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    input_name = State()
    choosing_phone_method = State()  # Выбор способа ввода телефона
    input_phone = State()
    waiting_comment_choice = State()
    input_comment = State()
    confirmation = State()
    
    # Состояния для редактирования при подтверждении
    edit_service = State()
    edit_date = State()
    edit_time = State()
    edit_name = State()
    edit_phone = State()
    edit_comment = State()


class EditBookingState(StatesGroup):
    """Состояния для редактирования существующего заказа"""
    choosing_action = State()  # Выбор: изменить дату/время или услугу
    choosing_date = State()
    choosing_time = State()
    choosing_service = State()
    confirmation = State()
