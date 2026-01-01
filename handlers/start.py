
"""Обработчик команды /start и главное меню"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

logger = logging.getLogger(__name__)

router = Router()


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создание главной клавиатуры с навигацией"""
    buttons = [
        [
            KeyboardButton(text="◀️ Назад"),
            KeyboardButton(text="📅 Записаться")
        ],
        [
            KeyboardButton(text="💅 Услуги и цены"),
            KeyboardButton(text="📋 Мои записи")
        ],
        [
            KeyboardButton(text="👩‍🎨 Мастера"),
            KeyboardButton(text="🎁 Акции")
        ],
        [
            KeyboardButton(text="ℹ️ О нас"),
            KeyboardButton(text="❓ FAQ")
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, config: dict):
    """Обработчик команды /start"""
    await state.clear()

    business_name = config.get('business_name', 'наш бизнес')
    welcome_message = config.get('messages', {}).get('welcome',
        f"Добро пожаловать в {business_name}! 👋\n\nВыберите действие:")

    keyboard = get_main_keyboard()

    await message.answer(welcome_message, reply_markup=keyboard)
    logger.info(f"User {message.from_user.id} started bot")


@router.message(Command("menu"))
@router.message(F.text.in_(["🏠 Меню", "🏠 Главное меню"]))
async def cmd_menu(message: Message, state: FSMContext, config: dict):
    """Возврат в главное меню"""
    await state.clear()
    business_name = config.get('business_name', 'наш бизнес')
    await message.answer(f"🏠 Главное меню «{business_name}»", reply_markup=get_main_keyboard())


@router.message(F.text == "◀️ Назад")
async def cmd_back(message: Message, state: FSMContext, config: dict):
    current_state = await state.get_state()
    data = await state.get_data()

    # Импортируем здесь, чтобы избежать циклических импортов
    from handlers.booking import generate_dates_keyboard
    from states.booking import BookingState

    # Если пользователь в календаре, выходим из него и возвращаемся к быстрым датам
    if data.get('using_calendar'):
        await state.update_data(using_calendar=False)
        keyboard = generate_dates_keyboard(config=config, master_id=data.get('master_id'))
        await message.answer("Выберите дату:", reply_markup=keyboard)
        await state.set_state(BookingState.choosing_date)
        return

    if not current_state:
        await cmd_menu(message, state, config)
        return

    # Остальная логика "Назад" без изменений
    from handlers.booking import (
        start_booking_flow,
        show_services_list,
        get_masters_for_service,
        show_confirmation
    )

    state_name = current_state.split(':')[0]

    if state_name == "BookingState":
        if current_state == BookingState.choosing_service:
            await start_booking_flow(message, state, config)
        elif current_state == BookingState.choosing_master:
            services = config.get('services', [])
            await show_services_list(message, state, config, services)
        elif current_state == BookingState.choosing_date:
            service_id = data.get('service_id')
            staff_enabled = config.get('staff', {}).get('enabled', False)
            masters = get_masters_for_service(config, service_id) if staff_enabled else []
            if masters and not data.get('booking_with_preselected_master'):
                buttons = [([InlineKeyboardButton(text=f"👤 {m['name']}", callback_data=f"master:{m['id']}")]) for m in masters]
                buttons.append([InlineKeyboardButton(text="👥 Любой свободный мастер", callback_data="master:any")])
                await message.answer("Выберите мастера:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
                await state.set_state(BookingState.choosing_master)
            else:
                services = config.get('services', [])
                await show_services_list(message, state, config, services)
        elif current_state == BookingState.choosing_time:
            master_id = data.get('master_id')
            keyboard = generate_dates_keyboard(config=config, master_id=master_id)
            await message.answer("Выберите дату:", reply_markup=keyboard)
            await state.set_state(BookingState.choosing_date)
        elif current_state in [BookingState.input_name, BookingState.input_phone, BookingState.input_comment]:
            await show_confirmation(message, state, config)
        else:
            await state.clear()
            await message.answer("❌ Действие отменено\n\n🏠 Главное меню:", reply_markup=get_main_keyboard())
    else:
        await cmd_menu(message, state, config)
