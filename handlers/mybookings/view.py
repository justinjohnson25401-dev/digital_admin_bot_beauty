
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from .keyboards import format_bookings_list

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("mybookings"))
@router.message(F.text == "📋 Мои записи")
async def show_my_bookings_handler(message: Message, db_manager, state: FSMContext, config: dict = None):
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

    text, keyboard = format_bookings_list(bookings, config)
    await message.answer(text, reply_markup=keyboard)
    logger.info(f"User {user_id} viewed their bookings ({len(bookings)} active)")

@router.callback_query(F.data == "back_to_mybookings")
async def back_to_mybookings_handler(callback: CallbackQuery, state: FSMContext, db_manager, config: dict = None):
    """Возврат к списку записей и его обновление"""
    await state.clear()
    user_id = callback.from_user.id
    bookings = db_manager.get_user_bookings(user_id, active_only=True)

    text, keyboard = format_bookings_list(bookings, config)
    
    # Используем edit_text, если сообщение не изменилось, иначе - answer
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)
        
    logger.info(f"User {user_id} returned to bookings list ({len(bookings)} active)")
    await callback.answer()
