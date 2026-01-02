"""
Выбор мастера (если staff enabled).
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from states.booking import BookingState
from .keyboards import get_masters_keyboard
from .utils import get_master_by_id
from .date import proceed_to_date_selection

logger = logging.getLogger(__name__)

router = Router()

async def show_masters_for_service(callback: CallbackQuery, state: FSMContext, config: dict, service: dict):
    """Показывает список мастеров для выбранной услуги."""
    from .utils import get_masters_for_service # Local import
    masters = get_masters_for_service(config, service['id'])
    keyboard = get_masters_keyboard(masters)
    await callback.message.edit_text(f"✅ {service['name']} — {service['price']}₽\n\nВыберите мастера:", reply_markup=keyboard)
    await state.set_state(BookingState.choosing_master)

@router.callback_query(BookingState.choosing_master, F.data.startswith("master:"))
async def master_selected(callback: CallbackQuery, state: FSMContext, config: dict):
    """Обрабатывает выбор мастера."""
    master_id = callback.data.split(":")[1]
    data = await state.get_data()
    service = {'name': data['service_name'], 'price': data['price']}
    
    if master_id == "any":
        await state.update_data(master_id=None, master_name="Любой мастер")
    else:
        master = get_master_by_id(config, master_id)
        if not master:
            await callback.answer("Мастер не найден", show_alert=True)
            return
        await state.update_data(master_id=master_id, master_name=master['name'])

    await proceed_to_date_selection(callback, state, config, service)
    await callback.answer()
