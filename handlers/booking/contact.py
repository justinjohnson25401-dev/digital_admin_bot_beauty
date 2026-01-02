"""
Ввод телефона и комментария.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from utils.validators import is_valid_phone, clean_phone
from .keyboards import get_cancel_keyboard, get_phone_input_keyboard, get_comment_choice_keyboard
from .confirmation import show_confirmation

logger = logging.getLogger(__name__)

router = Router()

async def request_contact_info(callback: CallbackQuery, state: FSMContext, db_manager):
    last_details = db_manager.get_last_client_details(callback.from_user.id)
    if last_details and last_details.get('client_name') and last_details.get('phone'):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Использовать", callback_data="reuse_details"),
             InlineKeyboardButton(text="✏️ Ввести заново", callback_data="enter_details")]])
        await callback.message.answer(f"Использовать данные с прошлой записи?\nИмя: {last_details['client_name']}\nТелефон: {last_details['phone']}", reply_markup=keyboard)
    else:
        await request_name_input(callback.message, state)
    await state.set_state(BookingState.input_name)

async def request_name_input(message: Message, state: FSMContext):
    await message.answer("Как вас зовут?", reply_markup=get_cancel_keyboard())

@router.callback_query(BookingState.input_name, F.data == "reuse_details")
async def reuse_last_details(callback: CallbackQuery, state: FSMContext, db_manager):
    last_details = db_manager.get_last_client_details(callback.from_user.id)
    if last_details:
        await state.update_data(client_name=last_details['client_name'], phone=last_details['phone'])
        logger.info(f"User {callback.from_user.id} reused previous details")
        await callback.message.edit_text(f"✅ Данные:\nИмя: {last_details['client_name']}\nТелефон: {last_details['phone']}")
        await ask_for_comment(callback.message, state)
    else:
        await request_name_input(callback.message, state)
    await callback.answer()

@router.callback_query(BookingState.input_name, F.data == "enter_details")
async def enter_details_manually(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Как вас зовут?")
    await callback.message.answer("Введите ваше имя:", reply_markup=get_cancel_keyboard())
    await callback.answer()

@router.message(BookingState.input_name, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_name(message: Message, state: FSMContext, config: dict):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 100:
        await message.answer("Имя должно содержать от 2 до 100 символов. Попробуйте снова:")
        return
    await state.update_data(client_name=name)
    logger.info(f"User {message.from_user.id} entered name in booking FSM")
    require_phone = config.get('features', {}).get('require_phone', True)
    if require_phone:
        await message.answer("📱 Как вы хотите указать номер телефона?", reply_markup=get_phone_input_keyboard())
        await state.set_state(BookingState.choosing_phone_method)
    else:
        await state.update_data(phone="не указан")
        await ask_for_comment(message, state)

@router.message(BookingState.choosing_phone_method, F.text == "✏️ Ввести вручную")
async def choose_manual_phone(message: Message, state: FSMContext):
    await message.answer("📞 Введите ваш номер телефона:", reply_markup=get_cancel_keyboard())
    await state.set_state(BookingState.input_phone)

@router.message(BookingState.choosing_phone_method, F.contact)
async def process_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=clean_phone(phone))
    logger.info(f"User {message.from_user.id} shared contact in booking FSM")
    await ask_for_comment(message, state)

@router.message(BookingState.input_phone, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_phone(message: Message, state: FSMContext):
    phone = clean_phone(message.text)
    if not is_valid_phone(phone):
        await message.answer("❌ Неверный формат номера. Введите в формате +7XXXXXXXXXX или 8XXXXXXXXXX:")
        return
    await state.update_data(phone=phone)
    logger.info(f"User {message.from_user.id} entered phone in booking FSM")
    await ask_for_comment(message, state)

async def ask_for_comment(message: Message, state: FSMContext):
    await message.answer("💬 Хотите добавить комментарий к записи?", reply_markup=get_comment_choice_keyboard())
    await state.set_state(BookingState.waiting_comment_choice)

@router.callback_query(BookingState.waiting_comment_choice, F.data == "add_comment")
async def want_add_comment(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💬 Введите ваш комментарий:")
    await state.set_state(BookingState.input_comment)
    await callback.answer()

@router.callback_query(BookingState.waiting_comment_choice, F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext, config: dict, db_manager):
    await state.update_data(comment=None)
    await callback.answer()
    await show_confirmation(callback.message, state, config, edit=True)

@router.message(BookingState.input_comment, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_comment(message: Message, state: FSMContext, config: dict):
    comment = message.text.strip()
    if len(comment) > 500:
        await message.answer("Комментарий слишком длинный (до 500 символов). Попробуйте снова:")
        return
    await state.update_data(comment=comment)
    logger.info(f"User {message.from_user.id} entered comment in booking FSM")
    await show_confirmation(message, state, config)
