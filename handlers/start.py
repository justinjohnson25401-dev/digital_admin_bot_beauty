
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


# === ГРУППА A: Хэндлеры кнопок главного меню ===

@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message, config: dict):
    """Показать FAQ"""
    faq_list = config.get('faq', [])
    faq_text = config.get('messages', {}).get('faq', '')

    if faq_text:
        # Если есть готовый текст FAQ
        text = f"❓ <b>Часто задаваемые вопросы</b>\n\n{faq_text}"
    elif faq_list:
        # Если FAQ в виде списка вопросов-ответов
        text = "❓ <b>Часто задаваемые вопросы</b>\n\n"
        for i, item in enumerate(faq_list, 1):
            q = item.get('question', item.get('btn', ''))
            a = item.get('answer', '')
            text += f"<b>{i}. {q}</b>\n{a}\n\n"
    else:
        text = "❓ Раздел FAQ пока не заполнен.\n\nСвяжитесь с нами для получения информации."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)
    logger.info(f"User {message.from_user.id} viewed FAQ")


@router.message(F.text == "🎁 Акции")
async def show_promotions(message: Message, config: dict):
    """Показать акции"""
    promotions = config.get('messages', {}).get('promotions', '')

    if promotions:
        text = f"🎁 <b>Акции и спецпредложения</b>\n\n{promotions}"
    else:
        text = "🎁 <b>Акции и спецпредложения</b>\n\nАкций пока нет. Следите за обновлениями!"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)
    logger.info(f"User {message.from_user.id} viewed promotions")


@router.message(F.text == "💅 Услуги и цены")
async def show_services(message: Message, config: dict):
    """Показать услуги и цены"""
    services = config.get('services', [])
    categories = config.get('categories', [])

    if not services:
        text = "💅 <b>Услуги и цены</b>\n\nСписок услуг пока не заполнен."
    else:
        text = "💅 <b>Услуги и цены</b>\n\n"

        # Группируем по категориям если есть
        if categories:
            for category in categories:
                cat_id = category.get('id', '')
                cat_name = category.get('name', '')
                cat_services = [s for s in services if s.get('category') == cat_id]

                if cat_services:
                    text += f"<b>{cat_name}</b>\n"
                    for service in cat_services:
                        name = service.get('name', '')
                        price = service.get('price', 0)
                        duration = service.get('duration', '')
                        dur_text = f" ({duration} мин)" if duration else ""
                        text += f"  • {name} — {price}₽{dur_text}\n"
                    text += "\n"

            # Услуги без категории
            no_cat_services = [s for s in services if not s.get('category')]
            if no_cat_services:
                for service in no_cat_services:
                    name = service.get('name', '')
                    price = service.get('price', 0)
                    duration = service.get('duration', '')
                    dur_text = f" ({duration} мин)" if duration else ""
                    text += f"• {name} — {price}₽{dur_text}\n"
        else:
            # Просто список услуг
            for service in services:
                name = service.get('name', '')
                price = service.get('price', 0)
                duration = service.get('duration', '')
                dur_text = f" ({duration} мин)" if duration else ""
                text += f"• {name} — {price}₽{dur_text}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться", callback_data="start_booking")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)
    logger.info(f"User {message.from_user.id} viewed services")


@router.message(F.text == "👩‍🎨 Мастера")
async def show_masters(message: Message, config: dict):
    """Показать список мастеров"""
    staff = config.get('staff', {})
    staff_enabled = staff.get('enabled', False)
    masters = staff.get('masters', [])

    if not staff_enabled or not masters:
        text = "👩‍🎨 <b>Наши мастера</b>\n\nИнформация о мастерах скоро появится."
    else:
        text = "👩‍🎨 <b>Наши мастера</b>\n\n"

        active_masters = [m for m in masters if m.get('active', True)]

        for master in active_masters:
            name = master.get('name', '')
            role = master.get('role', master.get('specialization', ''))
            description = master.get('description', '')

            text += f"<b>👤 {name}</b>"
            if role:
                text += f" — {role}"
            text += "\n"

            if description:
                text += f"   {description}\n"

            # Показать услуги мастера
            master_services = master.get('services', [])
            if master_services:
                all_services = config.get('services', [])
                service_names = []
                for sid in master_services:
                    for s in all_services:
                        if s.get('id') == sid:
                            service_names.append(s.get('name', ''))
                            break
                if service_names:
                    text += f"   Услуги: {', '.join(service_names)}\n"

            text += "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться", callback_data="start_booking")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)
    logger.info(f"User {message.from_user.id} viewed masters")


@router.message(F.text == "ℹ️ О нас")
async def show_about(message: Message, config: dict):
    """Показать информацию о компании"""
    about = config.get('messages', {}).get('about', '')
    business_name = config.get('business_name', '')
    contacts = config.get('contacts', {})

    if about:
        text = f"ℹ️ <b>О нас</b>\n\n{about}"
    else:
        text = f"ℹ️ <b>{business_name}</b>\n\n"

        if contacts:
            if contacts.get('address'):
                text += f"📍 Адрес: {contacts['address']}\n"
            if contacts.get('phone'):
                text += f"📞 Телефон: {contacts['phone']}\n"
            if contacts.get('email'):
                text += f"📧 Email: {contacts['email']}\n"
            if contacts.get('website'):
                text += f"🌐 Сайт: {contacts['website']}\n"
            if contacts.get('instagram'):
                text += f"📸 Instagram: {contacts['instagram']}\n"

        if not contacts:
            text += "Добро пожаловать! Мы рады видеть вас."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться", callback_data="start_booking")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)
    logger.info(f"User {message.from_user.id} viewed about")


@router.callback_query(F.data == "back_to_main_menu")
async def callback_back_to_main_menu(callback: CallbackQuery, state: FSMContext, config: dict):
    """Возврат в главное меню через inline-кнопку"""
    await state.clear()
    business_name = config.get('business_name', 'наш бизнес')
    await callback.message.answer(f"🏠 Главное меню «{business_name}»", reply_markup=get_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "start_booking")
async def callback_start_booking(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать бронирование через inline-кнопку"""
    from handlers.booking import start_booking_flow
    await start_booking_flow(callback.message, state, config)
    await callback.answer()


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
