"""
Обработчик команды /start, главного меню и общих информационных разделов.
"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

# Импортируем клавиатуры из центрального модуля
from .booking.keyboards import get_main_keyboard, get_info_keyboard
# Импортируем навигатор для кнопки "Назад" и функцию старта бронирования
from .booking.router_nav import navigate_back
from .booking.category import start_booking_flow
# Импортируем обработчик "Моих записей"
from .my_records import show_my_records

logger = logging.getLogger(__name__)
router = Router()

async def show_main_menu(message: Message, config: dict):
    """Отправляет главное меню.
       Вынесено в отдельную функцию для переиспользования.
    """
    welcome_template = config.get('messages', {}).get('welcome', "Добро пожаловать!")
    business_name = config.get('business_name', 'наш салон')
    welcome_message = welcome_template.format(business_name=business_name)
    
    keyboard = get_main_keyboard()
    await message.answer(welcome_message, reply_markup=keyboard)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, config: dict):
    """Обработчик команды /start."""
    await state.clear()
    await show_main_menu(message, config)
    logger.info(f"User {message.from_user.id} started bot")

@router.message(Command("menu"))
@router.message(F.text.in_(["🏠 Меню", "🏠 Главное меню", "Отмена"]))
async def cmd_menu(message: Message, state: FSMContext, config: dict):
    """Возврат в главное меню по команде или текстовой кнопке."""
    business_name = config.get('business_name', ' ')
    await state.clear()
    await message.answer(f"🏠 Главное меню «{business_name}»", reply_markup=get_main_keyboard())


# --- ОБРАБОТЧИКИ КНОПОК ГЛАВНОГО МЕНЮ ---

@router.message(F.text == "📅 Записаться")
async def cmd_start_booking(message: Message, state: FSMContext, config: dict):
    """Запускает процесс бронирования из главного меню."""
    await start_booking_flow(message, state, config)

@router.message(F.text == "📋 Мои записи")
async def cmd_my_records(message: Message, db_manager, config: dict):
    """Показывает раздел 'Мои записи'."""
    await show_my_records(message, db_manager, config)

@router.callback_query(F.data == "start_booking")
async def callback_start_booking(callback: CallbackQuery, state: FSMContext, config: dict):
    """Запускает процесс бронирования через inline-кнопку."""
    await start_booking_flow(callback.message, state, config)
    await callback.answer()

@router.message(F.text == "◀️ Назад")
async def cmd_back(message: Message, state: FSMContext, config: dict, db_manager):
    """Обрабатывает кнопку 'Назад', делегируя логику навигатору."""
    current_state = await state.get_state()
    if not current_state:
        await cmd_menu(message, state, config)
        return
    await navigate_back(message, state, config, db_manager)


# === Информационные разделы ===

@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message, config: dict):
    """Отображает раздел FAQ с форматированием."""
    faq_items = config.get('faq', [])
    if not faq_items:
        await message.answer("Раздел FAQ пока не заполнен.", reply_markup=get_info_keyboard(False))
        return

    # Данные для форматирования
    format_data = {
        'phone': config.get('contacts', {}).get('phone', 'номер не указан')
    }

    faq_text = ""
    for item in faq_items:
        answer = item.get('answer', '').format(**format_data)
        faq_text += f"<b>{item.get('btn')}</b>\n{answer}\n\n"

    keyboard = get_info_keyboard(add_booking_button=False)
    await message.answer(f"❓ <b>Часто задаваемые вопросы</b>\n\n{faq_text}", reply_markup=keyboard)

@router.message(F.text == "🎁 Акции")
async def show_promotions(message: Message, config: dict):
    promotions = config.get('messages', {}).get('promotions', "Акций пока нет. Следите за обновлениями!")
    keyboard = get_info_keyboard()
    await message.answer(f"🎁 <b>Акции и спецпредложения</b>\n\n{promotions}", reply_markup=keyboard)

@router.message(F.text == "💅 Услуги и цены")
async def show_services_pricelist(message: Message, config: dict):
    services = config.get('services', [])
    if not services:
        await message.answer("Список услуг пока не заполнен.", reply_markup=get_info_keyboard(False))
        return
    
    text = "💅 <b>Услуги и цены</b>\n\n"
    categorized_services = {}
    for service in services:
        category = service.get('category', 'Без категории')
        if category not in categorized_services: categorized_services[category] = []
        categorized_services[category].append(service)

    for category, items in categorized_services.items():
        text += f"<b>— {category} —</b>\n"
        for service in items:
            text += f"{service['name']} - {service['price']}\n"
        text += "\n"
    
    await message.answer(text, reply_markup=get_info_keyboard())

@router.message(F.text == "👩‍🎨 Мастера")
async def show_masters_list(message: Message, config: dict):
    staff_config = config.get('staff', {})
    if not staff_config.get('enabled') or not staff_config.get('list'):
        await message.answer("Информация о мастерах сейчас недоступна.", reply_markup=get_info_keyboard(False))
        return
    
    text = "<b>Наши мастера:</b>\n\n"
    for master in staff_config.get('list', []):
        text += f"<b>{master['name']}</b>\n{master.get('specialization', 'Специализация не указана')}\n\n"
    
    await message.answer(text, reply_markup=get_info_keyboard())

@router.message(F.text == "ℹ️ О нас")
async def show_about(message: Message, config: dict):
    """Отображает информацию 'О нас' с форматированием."""
    business_name = config.get('business_name', 'Наша компания')
    contacts = config.get('contacts', {})
    about_msg = config.get('messages', {}).get('about')

    text = f"<b>О нас: «{business_name}»</b>\n\n"
    if contacts.get('address'): 
        text += f"📍 <b>Адрес:</b> {contacts.get('address')}\n"
    if contacts.get('phone'): 
        text += f"📞 <b>Телефон:</b> {contacts.get('phone')}\n"
    if contacts.get('website'): 
        text += f"🌐 <b>Сайт:</b> {contacts.get('website')}\n"
    if about_msg: 
        text += f"\n{about_msg}"
    
    await message.answer(text, reply_markup=get_info_keyboard())

@router.callback_query(F.data == "back_to_main_menu")
async def callback_back_to_main_menu(callback: CallbackQuery, state: FSMContext, config: dict):
    """Возврат в главное меню через inline-кнопку."""
    await state.clear()
    await callback.message.delete() # Удаляем предыдущее сообщение
    await show_main_menu(callback.message, config)
    await callback.answer()
