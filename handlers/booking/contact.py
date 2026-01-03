"""
Обработчики для ввода контактной информации.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.booking import BookingState
from .confirmation import show_confirmation

logger = logging.getLogger(__name__)

router = Router()

async def request_contact_info(callback_or_message, state: FSMContext, db_manager):
    """Asks the user for their name and phone number."""
    message = callback_or_message if isinstance(callback_or_message, Message) else callback_or_message.message
    user_id = message.from_user.id
    
    # Check if user contact info already exists in the database
    user_info = db_manager.get_user_contact_info(user_id)
    
    if user_info and user_info.get('name') and user_info.get('phone'):
        await state.update_data(name=user_info['name'], phone=user_info['phone'])
        await show_confirmation(message, state)
    else:
        await message.answer("Пожалуйста, введите ваше имя:")
        await state.set_state(BookingState.input_name)

@router.message(BookingState.input_name, F.text)
async def name_entered(message: Message, state: FSMContext):
    """Handles the user entering their name."""
    await state.update_data(name=message.text)
    logger.info(f"User {message.from_user.id} entered name: {message.text}")
    await message.answer("Теперь, пожалуйста, введите ваш номер телефона (например, +79123456789):")
    await state.set_state(BookingState.input_phone)

@router.message(BookingState.input_phone, F.text)
async def phone_entered(message: Message, state: FSMContext, db_manager):
    """Handles the user entering their phone number."""
    # Basic validation could be added here
    await state.update_data(phone=message.text)
    logger.info(f"User {message.from_user.id} entered phone: {message.text}")
    
    # Save/update user contact info in the database
    user_id = message.from_user.id
    data = await state.get_data()
    db_manager.update_user_contact_info(user_id, data.get('name'), data.get('phone'))

    await message.answer("Вы хотите добавить комментарий к записи? (необязательно)")
    await state.set_state(BookingState.input_comment)

@router.message(BookingState.input_comment, F.text)
async def comment_entered(message: Message, state: FSMContext):
    """Handles the user entering a comment."""
    await state.update_data(comment=message.text)
    logger.info(f"User {message.from_user.id} entered comment: {message.text}")
    await show_confirmation(message, state)
