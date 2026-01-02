"""
Финальное подтверждение.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from .keyboards import get_confirmation_keyboard
from .utils import format_booking_summary

logger = logging.getLogger(__name__)

router = Router()

async def show_confirmation(message: Message, state: FSMContext, config: dict, edit: bool = False):
    """Показывает итоговую карточку бронирования для подтверждения."""
    data = await state.get_data()
    summary_text = format_booking_summary(data)
    keyboard = get_confirmation_keyboard()

    await state.set_state(BookingState.confirmation)

    if edit:
        await message.edit_text(summary_text, reply_markup=keyboard)
    else:
        from handlers.start import get_main_keyboard
        await message.answer(summary_text, reply_markup=keyboard)
        await message.answer("⬇️", reply_markup=get_main_keyboard())

@router.callback_query(BookingState.confirmation, F.data == "edit_name")
async def edit_name_in_confirmation(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите новое имя:")
    await state.set_state(BookingState.edit_name)
    await callback.answer()

@router.callback_query(BookingState.confirmation, F.data == "edit_phone")
async def edit_phone_in_confirmation(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✏️ Введите новый номер телефона:")
    await state.set_state(BookingState.edit_phone)
    await callback.answer()

@router.message(BookingState.edit_name, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_edit_name(message: Message, state: FSMContext, config: dict):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 100:
        await message.answer("Имя должно быть от 2 до 100 символов. Попробуйте снова:")
        return
    await state.update_data(client_name=name)
    await show_confirmation(message, state, config)

@router.message(BookingState.edit_phone, F.text, ~F.text.in_({"❌ Отменить", "◀️ Назад"}))
async def process_edit_phone(message: Message, state: FSMContext, config: dict):
    from utils.validators import is_valid_phone, clean_phone
    phone = clean_phone(message.text)
    if not is_valid_phone(phone):
        await message.answer("❌ Неверный формат. Введите номер в формате +7XXXXXXXXXX:")
        return
    await state.update_data(phone=phone)
    await show_confirmation(message, state, config)
