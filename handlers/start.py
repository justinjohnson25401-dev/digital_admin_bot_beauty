"""Обработчик команды /start и главное меню"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

logger = logging.getLogger(__name__)

router = Router()


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создание главной клавиатуры (5 кнопок по ТЗ)"""
    buttons = [
        [KeyboardButton(text="📅 Записаться")],
        [KeyboardButton(text="📋 Мои записи")],
        [KeyboardButton(text="💅 Услуги и цены")],
        [
            KeyboardButton(text="📍 Адрес"),
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
@router.message(F.text == "🏠 Главное меню")
async def cmd_menu(message: Message, state: FSMContext, config: dict):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_keyboard())


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext, config: dict):
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()


# ==================== УСЛУГИ И ЦЕНЫ ====================

@router.message(F.text == "💅 Услуги и цены")
async def show_services_prices(message: Message, config: dict):
    """Показ услуг и цен по категориям"""
    services = config.get('services', [])

    if not services:
        await message.answer("Список услуг пока не настроен.")
        return

    # Группируем услуги по категориям
    categories = {}
    for service in services:
        cat = service.get('category', 'Другое')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(service)

    # Формируем красивый текст
    text = "💅 <b>НАШИ УСЛУГИ И ЦЕНЫ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for cat_name, cat_services in categories.items():
        text += f"<b>📂 {cat_name}</b>\n"
        for svc in cat_services:
            duration = svc.get('duration', 0)
            duration_text = f" ({duration} мин)" if duration else ""
            text += f"  • {svc['name']} — <b>{svc['price']}₽</b>{duration_text}\n"
        text += "\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "📅 Для записи нажмите «Записаться»"

    # Кнопка быстрой записи
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться на услугу", callback_data="start_booking")]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "start_booking")
async def start_booking_from_services(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать запись из меню услуг"""
    # Импортируем функцию начала записи
    from handlers.booking import start_booking_flow
    await start_booking_flow(callback.message, state, config)
    await callback.answer()


# ==================== АДРЕС И КОНТАКТЫ ====================

@router.message(F.text == "📍 Адрес")
async def show_address(message: Message, config: dict):
    """Показ адреса и контактов"""
    contacts = config.get('contacts', {})
    address = contacts.get('address') or config.get('address', 'Адрес не указан')

    # Рабочие часы
    booking = config.get('booking', {})
    work_start = int(booking.get('work_start', 10))
    work_end = int(booking.get('work_end', 20))
    timezone_city = config.get('timezone_city', '')

    text = "📍 <b>КАК НАС НАЙТИ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"🏠 <b>Адрес:</b>\n{address}\n\n"
    text += f"🕐 <b>Режим работы:</b>\n"
    text += f"Ежедневно: {work_start:02d}:00 – {work_end:02d}:00\n"
    if timezone_city:
        text += f"<i>(время {timezone_city})</i>\n"

    # Дополнительные контакты если есть
    phone = contacts.get('phone')
    telegram = contacts.get('telegram')

    if phone or telegram:
        text += "\n📞 <b>Контакты:</b>\n"
        if phone:
            text += f"Телефон: {phone}\n"
        if telegram:
            text += f"Telegram: {telegram}\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━"

    await message.answer(text, parse_mode="HTML")


# ==================== FAQ ====================

@router.message(F.text.in_(["❓ FAQ", "❓ Часто задаваемые вопросы"]))
async def show_faq_menu(message: Message, config: dict):
    """Показ меню FAQ"""
    faq_items = config.get('faq', [])

    if not faq_items:
        await message.answer("FAQ пока не настроен.")
        return

    buttons = []
    for idx, item in enumerate(faq_items):
        btn_text = item.get('btn')
        if not btn_text:
            continue
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"faq:{idx}")])

    # Добавляем кнопку возврата в главное меню
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = "❓ <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>\n\nВыберите интересующий вас вопрос:"
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "faq_menu")
async def callback_faq_menu(callback: CallbackQuery, config: dict):
    """Возврат к меню FAQ по нажатию inline-кнопки"""
    faq_items = config.get('faq', [])

    if not faq_items:
        await callback.message.answer("FAQ пока не настроен.")
        await callback.answer()
        return

    buttons = []
    for idx, item in enumerate(faq_items):
        btn_text = item.get('btn')
        if not btn_text:
            continue
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"faq:{idx}")])

    # Добавляем кнопку возврата в главное меню
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = "❓ <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>\n\nВыберите интересующий вас вопрос:"
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("faq:"))
async def handle_faq_callback(callback: CallbackQuery, config: dict):
    """Выдача ответа на FAQ по нажатию inline-кнопки"""
    faq_items = config.get('faq', [])
    try:
        idx = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("Некорректный запрос", show_alert=True)
        return

    if idx < 0 or idx >= len(faq_items):
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    item = faq_items[idx] if idx < len(faq_items) else {}
    answer = item.get('answer') or "Ответ не найден."
    btn = (item.get('btn') or "").lower()

    # Динамическая генерация цен из услуг
    if 'цен' in btn or 'price' in btn:
        services = config.get('services', [])
        if services:
            answer = "💰 <b>Наши цены:</b>\n\n"
            # Группируем по категориям
            categories = {}
            for service in services:
                cat = service.get('category', 'Другое')
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(service)
            for cat_name, cat_services in categories.items():
                answer += f"<b>{cat_name}:</b>\n"
                for svc in cat_services:
                    answer += f"• {svc['name']} — {svc['price']}₽\n"
                answer += "\n"

    # Динамическая подстановка адреса
    if 'адрес' in btn:
        contacts = config.get('contacts', {})
        address = contacts.get('address') or config.get('address')
        if address:
            answer = f"📍 <b>Наш адрес:</b>\n{address}"

    # Динамический график работы
    if 'час' in btn or 'график' in btn or 'работ' in btn:
        booking = config.get('booking', {})
        work_start = int(booking.get('work_start', 10))
        work_end = int(booking.get('work_end', 20))
        answer = f"🕐 <b>Мы работаем:</b>\nЕжедневно: {work_start:02d}:00 – {work_end:02d}:00"

    # Кнопки навигации после ответа FAQ
    nav_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К списку вопросов", callback_data="faq_menu")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await callback.message.answer(answer, reply_markup=nav_keyboard, parse_mode="HTML")
    await callback.answer()


# Обратная совместимость со старой кнопкой
@router.message(F.text == "📅 Записаться / Заказать")
async def old_booking_button(message: Message, state: FSMContext, config: dict):
    """Обратная совместимость со старой кнопкой записи"""
    from handlers.booking import start_booking_flow
    await start_booking_flow(message, state, config)
