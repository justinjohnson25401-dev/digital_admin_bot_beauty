from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states.booking import EditBookingState
from utils.notify import send_order_change_to_admins, format_time
from handlers.booking import generate_dates_keyboard, generate_time_slots_keyboard
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = Router()


def _get_master_name(config: dict, master_id: str) -> str:
    """Получить имя мастера по ID из конфига"""
    if not master_id or not config:
        return None
    staff = config.get('staff', {})
    if not staff.get('enabled', False):
        return None
    for master in staff.get('masters', []):
        if master.get('id') == master_id:
            return master.get('name')
    return None


def _format_bookings_list(bookings: list, config: dict = None) -> tuple[str, InlineKeyboardMarkup]:
    """Форматирование списка записей и клавиатуры с отображением мастера"""
    text = "📋 <b>Ваши записи:</b>\n\n"

    for i, booking in enumerate(bookings, 1):
        booking_date = booking['booking_date']
        booking_time = booking['booking_time']
        client_name = booking.get('client_name')
        master_id = booking.get('master_id')

        if booking_date:
            try:
                date_obj = datetime.fromisoformat(booking_date)
                date_formatted = date_obj.strftime('%d.%m.%Y')
            except:
                date_formatted = booking_date
        else:
            date_formatted = "не указана"

        time_formatted = format_time(booking_time) if booking_time else 'не указано'

        text += f"<b>{i}. {booking['service_name']}</b>\n"

        # Показываем мастера если staff.enabled и есть master_id
        if master_id and config:
            master_name = _get_master_name(config, master_id)
            if master_name:
                text += f"   👤 Мастер: {master_name}\n"

        if client_name:
            text += f"   Имя: {client_name}\n"
        text += (
            f"   📅 Дата: {date_formatted}\n"
            f"   🕐 Время: {time_formatted}\n"
            f"   💰 Цена: {booking['price']}₽\n"
            f"   ID: #{booking['id']}\n\n"
        )

    buttons = []
    for booking in bookings:
        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ #{booking['id']}",
                callback_data=f"edit_booking:{booking['id']}"
            ),
            InlineKeyboardButton(
                text=f"🗑 #{booking['id']}",
                callback_data=f"cancel_order:{booking['id']}"
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    return text, keyboard

@router.message(Command("mybookings"))
async def show_my_bookings_command(message: Message, db_manager, state: FSMContext, config: dict = None):
    """Показать список записей пользователя (команда)"""
    await show_my_bookings(message, db_manager, state, config)

@router.message(F.text == "📋 Мои записи")
async def show_my_bookings_button(message: Message, db_manager, state: FSMContext, config: dict = None):
    """Показать список записей пользователя (кнопка)"""
    await show_my_bookings(message, db_manager, state, config)

async def show_my_bookings(message: Message, db_manager, state: FSMContext, config: dict = None):
    """Показать список записей пользователя"""
    await state.clear()
    user_id = message.from_user.id
    bookings = db_manager.get_user_bookings(user_id, active_only=True)

    if not bookings:
        await message.answer(
            "У вас пока нет активных записей.\n\n"
            "Используйте кнопку '📅 Записаться / Заказать' для создания новой записи."
        )
        return

    text, keyboard = _format_bookings_list(bookings, config)
    await message.answer(text, reply_markup=keyboard)
    logger.info(f"User {user_id} viewed their bookings ({len(bookings)} active)")

@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_handler(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработчик отмены заказа - запрос подтверждения"""
    order_id = int(callback.data.split(":")[1])
    
    # Получаем информацию о заказе
    order = db_manager.get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    
    # Форматируем дату и время
    try:
        from datetime import datetime
        date_obj = datetime.fromisoformat(order['booking_date'])
        date_formatted = date_obj.strftime('%d.%m.%Y')
    except:
        date_formatted = order['booking_date']
    
    time_formatted = order.get('booking_time', 'не указано')
    
    # Создаем клавиатуру с подтверждением
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel:{order_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="back_to_mybookings")
        ]
    ])
    
    text = (
        f"⚠️ Вы уверены, что хотите отменить запись?\n\n"
        f"📋 Услуга: {order['service_name']}\n"
        f"📅 Дата: {date_formatted}\n"
        f"🕐 Время: {time_formatted}\n\n"
        f"Это действие нельзя отменить."
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_cancel:"))
async def confirm_cancel_order_handler(callback: CallbackQuery, state: FSMContext, config: dict, db_manager, messages: dict, scheduler=None, admin_bot=None):
    """Подтверждение отмены заказа"""
    order_id = int(callback.data.split(":")[1])

    # Получаем информацию о заказе
    order = db_manager.get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    # Проверяем, что заказ принадлежит пользователю
    if order['user_id'] != callback.from_user.id:
        await callback.answer("Это не ваш заказ", show_alert=True)
        return

    # Проверяем статус
    if order['status'] != 'active':
        await callback.answer("Этот заказ уже отменён", show_alert=True)
        return

    # Отменяем заказ в БД
    success = db_manager.cancel_order(order_id)

    if success:
        # Отменяем напоминания (scheduler передается через middleware)
        if scheduler:
            try:
                scheduler.cancel_reminders(order_id)
            except Exception as e:
                logger.error(f"Error cancelling reminders: {e}")

        # Уведомляем админов (через админ-бота, если доступен)
        if config.get('features', {}).get('enable_admin_notify', True):
            notify_bot = admin_bot if admin_bot else callback.message.bot
            await notify_admin_about_cancellation(
                bot=notify_bot,
                admin_ids=config['admin_ids'],
                order=order,
                business_name=config['business_name'],
                db_manager=db_manager
            )

        # Форматирование времени
        formatted_time = format_time(order.get('booking_time', ''))

        # Сообщаем пользователю
        cancel_msg = messages.get('booking_cancelled', 'Запись отменена.')
        await callback.message.edit_text(
            f"{cancel_msg}\n\n"
            f"Отменённая запись:\n"
            f"• {order['service_name']}\n"
            f"• {order['booking_date']} {formatted_time}"
        )

        logger.info(f"Order {order_id} cancelled by user {callback.from_user.id}")
    else:
        await callback.answer("Ошибка отмены заказа", show_alert=True)

    await callback.answer()

# ИЗМЕНЕНО: Добавлен параметр db_manager для истории клиента (ошибка #3, #7)
async def notify_admin_about_cancellation(bot, admin_ids: list, order: dict, business_name: str, db_manager):
    """Уведомление администраторов об отмене"""
    # Форматирование времени
    formatted_time = format_time(order.get('booking_time', ''))

    message_text = (
        f"❌ Отмена записи в {business_name}\n\n"
        f"ID заявки: #{order['id']}\n"
        f"Услуга: {order['service_name']}\n"
        f"Дата: {order['booking_date']}\n"
        f"Время: {formatted_time}\n"
        f"Клиент: {order['client_name']}\n"
        f"Телефон: {order['phone']}\n"
    )

    # НОВОЕ: Добавляем историю клиента (ошибка #3)
    if db_manager:
        from utils.notify import get_client_history_text
        history_text = get_client_history_text(db_manager, order['user_id'], order['id'])
        if history_text:
            message_text += f"\n{history_text}"

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, message_text)
            logger.info(f"Cancellation notification sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id} about cancellation: {e}")

# === ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ СУЩЕСТВУЮЩИХ ЗАПИСЕЙ ===

@router.callback_query(F.data.startswith("edit_booking:"))
async def edit_booking_menu(callback: CallbackQuery, state: FSMContext, db_manager, config: dict):
    """Меню редактирования заказа"""
    order_id = int(callback.data.split(":")[1])
    order = db_manager.get_order_by_id(order_id)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    # Проверяем, что заказ принадлежит пользователю
    if order['user_id'] != callback.from_user.id:
        await callback.answer("Это не ваш заказ", show_alert=True)
        return

    # Проверяем статус
    if order['status'] != 'active':
        await callback.answer("Этот заказ уже отменён", show_alert=True)
        return

    # Сохраняем ID редактируемого заказа
    await state.update_data(editing_order_id=order_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Изменить дату и время",
                             callback_data=f"edit_datetime:{order_id}")],
        [InlineKeyboardButton(text="🔄 Изменить услугу",
                             callback_data=f"edit_service_existing:{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_mybookings")],
    ])

    # Форматирование времени
    formatted_time = format_time(order.get('booking_time', ''))

    # Форматирование даты
    try:
        date_obj = datetime.fromisoformat(order['booking_date'])
        formatted_date = date_obj.strftime('%d.%m.%Y')
    except:
        formatted_date = order['booking_date']

    await callback.message.edit_text(
        f"Редактирование заказа #{order_id}\n\n"
        f"Услуга: {order['service_name']}\n"
        f"Дата: {formatted_date}\n"
        f"Время: {formatted_time}\n\n"
        f"Цена: {order['price']}₽\n\n"
        "Что хотите изменить?",
        reply_markup=keyboard
    )

    await state.set_state(EditBookingState.choosing_action)
    await callback.answer()

@router.callback_query(EditBookingState.choosing_action, F.data.startswith("edit_datetime:"))
async def edit_datetime_start(callback: CallbackQuery, state: FSMContext):
    """Начало изменения даты и времени"""
    order_id = int(callback.data.split(":")[1])
    keyboard = generate_dates_keyboard()

    await callback.message.edit_text(
        "Выберите новую дату:",
        reply_markup=keyboard
    )

    await state.set_state(EditBookingState.choosing_date)
    await callback.answer()

@router.callback_query(EditBookingState.choosing_date, F.data.startswith("date:"))
async def edit_datetime_date_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора новой даты"""
    booking_date = callback.data.split(":")[1]
    await state.update_data(new_booking_date=booking_date)

    data = await state.get_data()
    order_id = data.get('editing_order_id')

    # ИЗМЕНЕНО: Передаём exclude_order_id для исключения текущего заказа (ошибка #4)
    # Генерируем слоты времени (исключая текущий заказ)
    keyboard = generate_time_slots_keyboard(config, db_manager, booking_date, exclude_order_id=order_id)

    date_obj = datetime.fromisoformat(booking_date)
    date_formatted = date_obj.strftime('%d.%m.%Y')

    await callback.message.edit_text(
        f"Дата: {date_formatted}\n\n"
        "Выберите новое время:",
        reply_markup=keyboard
    )

    await state.set_state(EditBookingState.choosing_time)
    await callback.answer()

@router.callback_query(EditBookingState.choosing_time, F.data.startswith("time:"))
async def edit_datetime_time_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора нового времени"""
    booking_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    order_id = data.get('editing_order_id')
    new_booking_date = data.get('new_booking_date')

    # Проверка доступности (исключая текущий заказ)
    if not db_manager.check_slot_availability_excluding(new_booking_date, booking_time, order_id):
        await callback.answer("Это время уже занято. Выберите другой слот.", show_alert=True)
        return

    await state.update_data(new_booking_time=booking_time)

    # Получаем данные старого заказа
    old_order = db_manager.get_order_by_id(order_id)

    # Форматирование для отображения
    old_time = format_time(old_order.get('booking_time', ''))
    new_time = format_time(booking_time)

    try:
        old_date_obj = datetime.fromisoformat(old_order['booking_date'])
        old_date_formatted = old_date_obj.strftime('%d.%m.%Y')
    except:
        old_date_formatted = old_order['booking_date']

    try:
        new_date_obj = datetime.fromisoformat(new_booking_date)
        new_date_formatted = new_date_obj.strftime('%d.%m.%Y')
    except:
        new_date_formatted = new_booking_date

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить изменения", callback_data="confirm_edit")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="back_to_mybookings")]
    ])

    await callback.message.edit_text(
        f"Подтверждение изменений\n\n"
        f"Было:\n"
        f"├ Дата: {old_date_formatted}\n"
        f"└ Время: {old_time}\n\n"
        f"Будет:\n"
        f"├ Дата: {new_date_formatted}\n"
        f"└ Время: {new_time}\n\n"
        "Подтверждаете изменения?",
        reply_markup=keyboard
    )

    await state.set_state(EditBookingState.confirmation)
    await callback.answer()

@router.callback_query(EditBookingState.choosing_action, F.data.startswith("edit_service_existing:"))
async def edit_service_existing_start(callback: CallbackQuery, state: FSMContext, config: dict):
    """Начало изменения услуги"""
    order_id = int(callback.data.split(":")[1])
    services = config.get('services', [])

    buttons = []
    for service in services:
        button_text = f"{service['name']} — {service['price']}₽"
        callback_data = f"new_service:{service['id']}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_booking:{order_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выберите новую услугу:", reply_markup=keyboard)
    await state.set_state(EditBookingState.choosing_service)
    await callback.answer()

@router.callback_query(EditBookingState.choosing_service, F.data.startswith("new_service:"))
async def edit_service_selected(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    """Обработка выбора новой услуги"""
    service_id = callback.data.split(":")[1]
    services = config.get('services', [])

    selected_service = None
    for service in services:
        if service['id'] == service_id:
            selected_service = service
            break

    if not selected_service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        new_service_id=selected_service['id'],
        new_service_name=selected_service['name'],
        new_price=selected_service['price']
    )

    data = await state.get_data()
    order_id = data.get('editing_order_id')
    old_order = db_manager.get_order_by_id(order_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить изменения", callback_data="confirm_edit")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="back_to_mybookings")]
    ])

    await callback.message.edit_text(
        f"Подтверждение изменений\n\n"
        f"Было: {old_order['service_name']} — {old_order['price']}₽\n"
        f"Будет: {selected_service['name']} — {selected_service['price']}₽\n\n"
        "Подтверждаете изменения?",
        reply_markup=keyboard
    )

    await state.set_state(EditBookingState.confirmation)
    await callback.answer()

@router.callback_query(EditBookingState.confirmation, F.data == "confirm_edit")
async def confirm_order_edit(callback: CallbackQuery, state: FSMContext, config: dict, db_manager, scheduler=None, admin_bot=None):
    """Финальное подтверждение изменений"""
    data = await state.get_data()
    order_id = data.get('editing_order_id')

    # Получаем старые данные для уведомления
    old_order = db_manager.get_order_by_id(order_id)

    # Формируем обновления
    updates = {}
    if data.get('new_booking_date'):
        updates['booking_date'] = data['new_booking_date']
    if data.get('new_booking_time'):
        updates['booking_time'] = data['new_booking_time']
    if data.get('new_service_id'):
        updates['service_id'] = data['new_service_id']
        updates['service_name'] = data['new_service_name']
        updates['price'] = data['new_price']

    # Обновляем заказ
    success = db_manager.update_order(order_id, **updates)

    if success:
        # Получаем обновлённые данные
        new_order = db_manager.get_order_by_id(order_id)

        # Отменяем старые напоминания и создаём новые (если дата/время изменились)
        if scheduler and (data.get('new_booking_date') or data.get('new_booking_time')):
            try:
                scheduler.cancel_reminders(order_id)
                scheduler.schedule_reminders(
                    order_id=order_id,
                    user_id=callback.from_user.id,
                    service_name=new_order['service_name'],
                    booking_date=new_order['booking_date'],
                    booking_time=new_order['booking_time']
                )
            except Exception as e:
                logger.error(f"Error rescheduling reminders: {e}")

        # Уведомляем админов (через админ-бота, если доступен)
        if config.get('features', {}).get('enable_admin_notify', True):
            notify_bot = admin_bot if admin_bot else callback.message.bot
            await send_order_change_to_admins(
                bot=notify_bot,
                admin_ids=config['admin_ids'],
                old_order=old_order,
                new_order=new_order,
                business_name=config['business_name'],
                db_manager=db_manager
            )

        await callback.message.edit_text("✅ Заказ успешно изменён!")

        user_id = callback.from_user.id
        bookings = db_manager.get_user_bookings(user_id, active_only=True)

        if bookings:
            text, keyboard = _format_bookings_list(bookings, config)
            await callback.message.answer(text, reply_markup=keyboard)
            logger.info(f"User {user_id} viewed updated bookings after edit")

        logger.info(f"Order {order_id} edited by user {callback.from_user.id}")
    else:
        await callback.message.edit_text("❌ Ошибка изменения заказа")

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "back_to_mybookings")
async def back_to_mybookings(callback: CallbackQuery, state: FSMContext, db_manager, config: dict = None):
    """Возврат к списку записей"""
    await state.clear()
    user_id = callback.from_user.id
    bookings = db_manager.get_user_bookings(user_id, active_only=True)

    if not bookings:
        await callback.message.edit_text(
            "📋 У вас пока нет активных записей.\n\n"
            "Используйте кнопку '📅 Записаться / Заказать' для создания новой записи."
        )
        await callback.answer()
        return

    text, keyboard = _format_bookings_list(bookings, config)
    await callback.message.answer(text, reply_markup=keyboard)
    logger.info(f"User {user_id} returned to bookings list ({len(bookings)} active)")
    await callback.answer()
