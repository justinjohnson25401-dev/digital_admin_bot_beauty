"""
Обработчики для выбора мастера.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from states.booking import BookingState
from ..keyboards import get_masters_keyboard # assuming keyboards are in handlers/booking/keyboards.py
from ..utils import get_masters_for_service, get_master_by_id # assuming utils are in handlers/booking/utils.py
from .date import proceed_to_date_selection

logger = logging.getLogger(__name__)

router = Router()

async def show_masters_for_service(callback_or_message, state: FSMContext, config: dict, service: dict):
    """Displays the list of masters available for a given service."""
    masters = get_masters_for_service(config, service['id'])
    
    # Decide if we're editing a message or sending a new one
    message = callback_or_message if isinstance(callback_or_message, Message) else callback_or_message.message

    if not masters:
        # No specific masters for this service, skip to date selection
        await state.update_data(master_id=None, master_name=None)
        await proceed_to_date_selection(callback_or_message, state, config, service)
        return

    keyboard = get_masters_keyboard(masters)
    await message.edit_text(f"Выберите мастера для услуги «{service['name']}»:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_master)

@router.callback_query(BookingState.choosing_master, F.data.startswith("master:"))
async def master_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    """Handles the selection of a master."""
    master_id = callback.data.split(":", 1)[1]
    
    if master_id == 'any':
        await state.update_data(master_id=None, master_name="Любой")
        master_name = "Любой мастер"
    else:
        master = get_master_by_id(config, master_id)
        if not master:
            await callback.answer("Мастер не найден", show_alert=True)
            return
        await state.update_data(master_id=master_id, master_name=master['name'])
        master_name = master['name']

    logger.info(f"User {callback.from_user.id} selected master: {master_name}")

    service_id = (await state.get_data()).get('service_id')
    service = next((s for s in config.get('services', []) if s['id'] == service_id), None)

    await proceed_to_date_selection(callback, state, config, service)
    await callback.answer()