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
    """Кнопка Назад - возврат к предыдущему шагу или в главное меню"""
    from states.booking import BookingState
    from handlers.booking import (
        get_categories_from_services, get_services_by_category,
        get_masters_for_service, generate_dates_keyboard,
        get_master_by_id
    )

    data = await state.get_data()
    current_state = await state.get_state()

    # Если есть история навигации - возвращаемся назад
    nav_history = data.get('nav_history', [])

    if nav_history:
        # Возвращаемся к предыдущему экрану
        prev_screen = nav_history.pop()
        await state.update_data(nav_history=nav_history)

        if prev_screen == 'masters_list':
            await show_masters_list(message, config)
            return
        elif prev_screen == 'master_profile':
            master_id = data.get('viewing_master_id')
            if master_id:
                master = get_master_by_id(config, master_id)
                if master:
                    await _show_master_profile_msg(message, config, master)
                    return
        elif prev_screen == 'services':
            await message.answer("💅 Услуги и цены", reply_markup=get_main_keyboard())
            await show_services_prices(message, config)
            return

    # Обработка состояний записи (BookingState)
    if current_state:
        services = config.get('services', [])
        categories = get_categories_from_services(services)

        # choosing_service → choosing_category (или главное меню)
        if current_state == BookingState.choosing_service.state:
            if len(categories) > 1:
                # Возвращаемся к категориям
                buttons = []
                for cat in categories:
                    buttons.append([InlineKeyboardButton(
                        text=f"📂 {cat}",
                        callback_data=f"cat:{cat}"
                    )])
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await message.answer("Выберите категорию услуг:", reply_markup=keyboard)
                await state.set_state(BookingState.choosing_category)
                return
            else:
                # Одна категория - выходим в меню
                await state.clear()
                await message.answer("🏠 Главное меню:", reply_markup=get_main_keyboard())
                return

        # choosing_category → главное меню
        elif current_state == BookingState.choosing_category.state:
            await state.clear()
            await message.answer("🏠 Главное меню:", reply_markup=get_main_keyboard())
            return

        # choosing_master → choosing_service
        elif current_state == BookingState.choosing_master.state:
            category = data.get('selected_category')
            if category:
                cat_services = get_services_by_category(services, category)
            else:
                cat_services = services

            buttons = []
            for svc in cat_services:
                duration = svc.get('duration', 0)
                dur_text = f" • {duration}мин" if duration else ""
                btn_text = f"{svc['name']} — {svc['price']}₽{dur_text}"
                buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srv:{svc['id']}")])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            title = f"📂 {category}\n\n" if category else ""
            await message.answer(f"{title}Выберите услугу:", reply_markup=keyboard)
            await state.set_state(BookingState.choosing_service)
            return

        # choosing_date → choosing_master (или choosing_service)
        elif current_state == BookingState.choosing_date.state:
            service_id = data.get('service_id')
            staff_enabled = config.get('staff', {}).get('enabled', False)
            masters = get_masters_for_service(config, service_id) if staff_enabled else []

            if masters and not data.get('booking_with_preselected_master'):
                # Возвращаемся к выбору мастера
                buttons = []
                for master in masters:
                    spec = master.get('specialization') or master.get('role', '')
                    spec_text = f" ({spec})" if spec else ""
                    buttons.append([InlineKeyboardButton(
                        text=f"👤 {master['name']}{spec_text}",
                        callback_data=f"master:{master['id']}"
                    )])
                buttons.append([InlineKeyboardButton(text="👥 Любой свободный мастер", callback_data="master:any")])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await message.answer(
                    f"✅ {data.get('service_name')} — {data.get('price')}₽\n\nВыберите мастера:",
                    reply_markup=keyboard
                )
                await state.set_state(BookingState.choosing_master)
                return
            else:
                # Возвращаемся к услугам
                category = data.get('selected_category')
                if category:
                    cat_services = get_services_by_category(services, category)
                else:
                    cat_services = services

                buttons = []
                for svc in cat_services:
                    duration = svc.get('duration', 0)
                    dur_text = f" • {duration}мин" if duration else ""
                    btn_text = f"{svc['name']} — {svc['price']}₽{dur_text}"
                    buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srv:{svc['id']}")])

                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await message.answer("Выберите услугу:", reply_markup=keyboard)
                await state.set_state(BookingState.choosing_service)
                return

        # choosing_time → choosing_date
        elif current_state == BookingState.choosing_time.state:
            master_id = data.get('master_id')
            keyboard = generate_dates_keyboard(config=config, master_id=master_id)
            await message.answer("Выберите дату:", reply_markup=keyboard)
            await state.set_state(BookingState.choosing_date)
            return

        # Остальные состояния - отмена записи
        await state.clear()
        await message.answer("❌ Действие отменено\n\n🏠 Главное меню:", reply_markup=get_main_keyboard())
    else:
        await message.answer("🏠 Главное меню:", reply_markup=get_main_keyboard())


async def _show_master_profile_msg(message: Message, config: dict, master: dict):
    """Показать профиль мастера (message версия для кнопки Назад)"""
    name = master.get('name', 'Мастер')
    position = master.get('position', '')
    experience = master.get('experience', '')
    specialization = master.get('specialization', '')
    about = master.get('about', '')
    master_services = master.get('services', [])
    master_id = master.get('id', '')

    text = f"👤 <b>{name}</b>\n"
    if position:
        text += f"{position}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if experience:
        text += f"⭐ <b>Опыт:</b> {experience}\n"
    if specialization:
        text += f"💅 <b>Специализация:</b> {specialization}\n"
    if about:
        text += f"\n📝 <b>О мастере:</b>\n{about}\n"

    if master_services:
        all_services = config.get('services', [])
        service_names = []
        for svc_id in master_services:
            svc = next((s for s in all_services if s.get('id') == svc_id), None)
            if svc:
                service_names.append(svc.get('name', svc_id))
        if service_names:
            text += f"\n🏷 <b>Услуги:</b> {', '.join(service_names)}\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━"

    buttons = [
        [InlineKeyboardButton(text=f"📅 Записаться к {name.split()[0]}", callback_data=f"book_master:{master_id}")],
        [InlineKeyboardButton(text="◀️ Все мастера", callback_data="masters_list")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


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


# ==================== О НАС ====================

@router.message(F.text.in_(["ℹ️ О нас", "📍 Адрес"]))
async def show_about(message: Message, config: dict):
    """Показ информации о компании"""
    business_name = config.get('business_name', 'Наш бизнес')
    about = config.get('about', {})
    contacts = config.get('contacts', {})

    # Основная информация
    text = f"ℹ️ <b>О НАС</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"✨ <b>{business_name}</b>\n\n"

    # Описание (из about или default)
    description = about.get('description', '')
    if description:
        text += f"{description}\n\n"

    # Специализация
    specialization = about.get('specialization', '')
    if specialization:
        text += f"💅 {specialization}\n\n"

    # Достижения
    achievements = about.get('achievements', '')
    if achievements:
        text += f"🏆 {achievements}\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Адрес
    address = contacts.get('address') or config.get('address', '')
    if address:
        text += f"📍 <b>Адрес:</b> {address}\n"

    # Рабочие часы
    booking = config.get('booking', {})
    work_start = int(booking.get('work_start', 10))
    work_end = int(booking.get('work_end', 20))
    timezone_city = config.get('timezone_city', '')
    text += f"🕐 <b>Режим работы:</b> {work_start:02d}:00 – {work_end:02d}:00"
    if timezone_city:
        text += f" ({timezone_city})"
    text += "\n"

    # Контакты
    phone = contacts.get('phone')
    telegram = contacts.get('telegram')
    instagram = contacts.get('instagram', '')
    website = contacts.get('website', '')

    if phone:
        text += f"📞 <b>Телефон:</b> {phone}\n"
    if telegram:
        text += f"💬 <b>Telegram:</b> {telegram}\n"
    if instagram:
        text += f"📸 <b>Instagram:</b> {instagram}\n"
    if website:
        text += f"🌐 <b>Сайт:</b> {website}\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━"

    await message.answer(text, parse_mode="HTML")


# ==================== НАШИ МАСТЕРА ====================

@router.message(F.text == "👩‍🎨 Мастера")
async def show_masters_list(message: Message, config: dict):
    """Показ списка мастеров"""
    staff_config = config.get('staff', {})

    if not staff_config.get('enabled', False):
        await message.answer("Информация о мастерах пока не добавлена.")
        return

    masters = staff_config.get('masters', [])
    if not masters:
        await message.answer("Список мастеров пуст.")
        return

    text = "👩‍🎨 <b>НАШИ МАСТЕРА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Выберите мастера, чтобы узнать подробнее:\n\n"

    buttons = []
    for master in masters:
        master_name = master.get('name', 'Мастер')
        master_id = master.get('id', '')
        # Специализация хранится в specialization или role
        specialization = master.get('specialization') or master.get('role', '')

        btn_text = f"👤 {master_name}"
        if specialization:
            btn_text += f" — {specialization}"

        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"master_info:{master_id}"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("master_info:"))
async def show_master_profile(callback: CallbackQuery, state: FSMContext, config: dict):
    """Показ профиля мастера"""
    master_id = callback.data.replace("master_info:", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m.get('id') == master_id), None)

    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return

    # Сохраняем для навигации назад
    data = await state.get_data()
    nav_history = data.get('nav_history', [])
    nav_history.append('masters_list')
    await state.update_data(nav_history=nav_history, viewing_master_id=master_id)

    name = master.get('name', 'Мастер')
    position = master.get('position', '')
    experience = master.get('experience', '')
    specialization = master.get('specialization', '')
    about = master.get('about', '')
    master_services = master.get('services', [])

    text = f"👤 <b>{name}</b>\n"
    if position:
        text += f"{position}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if experience:
        text += f"⭐ <b>Опыт:</b> {experience}\n"
    if specialization:
        text += f"💅 <b>Специализация:</b> {specialization}\n"
    if about:
        text += f"\n📝 <b>О мастере:</b>\n{about}\n"

    # Получаем русские названия услуг из конфига
    if master_services:
        all_services = config.get('services', [])
        service_names = []
        for svc_id in master_services:
            # Ищем услугу по ID
            svc = next((s for s in all_services if s.get('id') == svc_id), None)
            if svc:
                service_names.append(svc.get('name', svc_id))
            else:
                # Если не нашли, показываем как есть (но не ID)
                service_names.append(svc_id.replace('_', ' ').title())
        if service_names:
            text += f"\n🏷 <b>Услуги:</b> {', '.join(service_names)}\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━"

    # Кнопка записи к этому мастеру
    buttons = [
        [InlineKeyboardButton(text=f"📅 Записаться к {name.split()[0]}", callback_data=f"book_master:{master_id}")],
        [InlineKeyboardButton(text="◀️ Все мастера", callback_data="masters_list")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "masters_list")
async def callback_masters_list(callback: CallbackQuery, config: dict):
    """Возврат к списку мастеров"""
    staff_config = config.get('staff', {})
    masters = staff_config.get('masters', [])

    if not masters:
        await callback.answer("Список мастеров пуст", show_alert=True)
        return

    text = "👩‍🎨 <b>НАШИ МАСТЕРА</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Выберите мастера, чтобы узнать подробнее:\n\n"

    buttons = []
    for master in masters:
        master_name = master.get('name', 'Мастер')
        master_id = master.get('id', '')
        # Специализация хранится в specialization или role
        specialization = master.get('specialization') or master.get('role', '')

        btn_text = f"👤 {master_name}"
        if specialization:
            btn_text += f" — {specialization}"

        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"master_info:{master_id}"
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("book_master:"))
async def book_specific_master(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начать запись к конкретному мастеру"""
    master_id = callback.data.replace("book_master:", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m.get('id') == master_id), None)

    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return

    # Сохраняем выбранного мастера в state
    await state.update_data(selected_master_id=master_id, selected_master_name=master.get('name'))

    # Запускаем процесс записи с предвыбранным мастером
    from handlers.booking import start_booking_with_master
    await start_booking_with_master(callback.message, state, config, master_id)
    await callback.answer()


# ==================== АКЦИИ ====================

@router.message(F.text == "🎁 Акции")
async def show_promotions(message: Message, config: dict):
    """Показ текущих акций"""
    promotions = config.get('promotions', [])

    text = "🎁 <b>АКЦИИ И СПЕЦПРЕДЛОЖЕНИЯ</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not promotions:
        text += "🔜 Скоро здесь появятся выгодные предложения!\n\n"
        text += "Следите за обновлениями 😊"
    else:
        for promo in promotions:
            if not promo.get('active', True):
                continue

            emoji = promo.get('emoji', '🎁')
            title = promo.get('title', 'Акция')
            description = promo.get('description', '')
            valid_until = promo.get('valid_until', '')
            is_permanent = promo.get('is_permanent', False)

            text += f"{emoji} <b>{title}</b>\n"
            if description:
                text += f"   {description}\n"
            if is_permanent:
                text += "   <i>Действует: постоянно</i>\n"
            elif valid_until:
                text += f"   <i>Действует: до {valid_until}</i>\n"
            text += "\n"

    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "📅 Для записи нажмите «Записаться»"

    await message.answer(text, parse_mode="HTML")


# ==================== FAQ ====================

# Пункты FAQ, которые теперь в разделе "О нас"
FAQ_SKIP_ITEMS = ['часы работы', 'контакты', 'режим работы', 'адрес']


def get_developer_credit(config: dict) -> str:
    """Получить кредит разработчика из конфига"""
    dev_config = config.get('bot_settings', {}).get('developer_credit', {})
    if dev_config.get('enabled', True):
        contact = dev_config.get('contact', '@Oroani')
        text = dev_config.get('text', 'Разработчик бота')
        return f"\n━━━━━━━━━━━━━━━━━━━━━━\n🤖 {text}: {contact}"
    return ""


@router.message(F.text.in_(["❓ FAQ", "❓ Часто задаваемые вопросы"]))
async def show_faq_menu(message: Message, config: dict):
    """Показ меню FAQ"""
    faq_items = config.get('faq', [])

    if not faq_items:
        text = "❓ <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>\n\nFAQ пока не настроен."
        text += get_developer_credit(config)
        await message.answer(text, parse_mode="HTML")
        return

    buttons = []
    for idx, item in enumerate(faq_items):
        btn_text = item.get('btn', '')
        if not btn_text:
            continue
        # Пропускаем пункты, которые теперь в "О нас"
        if any(skip in btn_text.lower() for skip in FAQ_SKIP_ITEMS):
            continue
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"faq:{idx}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    text = "❓ <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>\n\nВыберите интересующий вас вопрос:"
    text += get_developer_credit(config)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "faq_menu")
async def callback_faq_menu(callback: CallbackQuery, config: dict):
    """Возврат к меню FAQ по нажатию inline-кнопки"""
    faq_items = config.get('faq', [])

    if not faq_items:
        text = "❓ <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>\n\nFAQ пока не настроен."
        text += get_developer_credit(config)
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()
        return

    buttons = []
    for idx, item in enumerate(faq_items):
        btn_text = item.get('btn', '')
        if not btn_text:
            continue
        # Пропускаем пункты, которые теперь в "О нас"
        if any(skip in btn_text.lower() for skip in FAQ_SKIP_ITEMS):
            continue
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"faq:{idx}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    text = "❓ <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>\n\nВыберите интересующий вас вопрос:"
    text += get_developer_credit(config)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
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

    # Навигация через нижнее меню - inline кнопки не нужны
    await callback.message.edit_text(answer, parse_mode="HTML")
    await callback.answer()


# Обратная совместимость со старой кнопкой
@router.message(F.text == "📅 Записаться / Заказать")
async def old_booking_button(message: Message, state: FSMContext, config: dict):
    """Обратная совместимость со старой кнопкой записи"""
    from handlers.booking import start_booking_flow
    await start_booking_flow(message, state, config)
