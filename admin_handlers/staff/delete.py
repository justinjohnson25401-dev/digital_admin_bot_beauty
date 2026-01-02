"""
Удаление мастера.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.config_editor import ConfigEditor
from .keyboards import _build_masters_list_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "delete_master_list")
async def show_delete_master_list(callback: CallbackQuery, config: dict):
    """Список мастеров для удаления"""

    masters = config.get('staff', {}).get('masters', [])

    if not masters:
        await callback.answer("Нет мастеров для удаления", show_alert=True)
        return

    text = "🗑 <b>УДАЛЕНИЕ МАСТЕРА</b>\n\nВыберите мастера для удаления:"
    keyboard = _build_masters_list_keyboard(masters, "delete_master")

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_master_"))
async def confirm_master_deletion(callback: CallbackQuery, config: dict, db_manager):
    """Подтверждение удаления мастера с проверкой активных записей"""

    master_id = callback.data.replace("delete_master_", "")

    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)

    if not master:
        await callback.answer("❌ Мастер не найден", show_alert=True)
        return

    active_orders_count = 0
    try:
        cursor = db_manager.connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM orders
            WHERE master_id = ? AND status = 'active'
            AND (booking_date IS NULL OR booking_date >= date('now'))
        """, (master_id,))
        active_orders_count = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error checking active orders for master {master_id}: {e}")

    warning_text = ""
    if active_orders_count > 0:
        warning_text = f"\n⚠️ <b>ВНИМАНИЕ:</b> У мастера {active_orders_count} активных записей!\nОни останутся в системе, но мастер не будет отображаться.\n"

    text = f"""
⚠️ <b>УДАЛЕНИЕ МАСТЕРА</b>

Вы уверены, что хотите удалить мастера?

👤 <b>{master['name']}</b>
💼 {master.get('specialization') or master.get('role', 'Мастер')}
{warning_text}
<i>Это действие нельзя отменить!</i>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_master_{master_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="delete_master_list")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_master_"))
async def delete_master(callback: CallbackQuery, config: dict, config_manager, state: FSMContext):
    """Выполнить удаление мастера с обработкой ошибок"""

    master_id = callback.data.replace("confirm_delete_master_", "")

    # Находим мастера для имени
    masters = config.get('staff', {}).get('masters', [])
    master = next((m for m in masters if m['id'] == master_id), None)
    master_name = master['name'] if master else 'Неизвестный'

    try:
        # Удаляем из конфига
        editor = ConfigEditor(config_manager.config_path)
        success = editor.delete_master(master_id)

        if not success:
            await callback.answer("❌ Не удалось удалить мастера", show_alert=True)
            return

        # Обновляем в памяти
        config['staff']['masters'] = [m for m in masters if m['id'] != master_id]
        config_manager.config['staff'] = config['staff']

        await callback.answer(f"✅ Мастер \"{master_name}\" удалён!")
        logger.info(f"Master {master_id} ({master_name}) deleted by admin {callback.from_user.id}")

    except Exception as e:
        logger.error(f"Error deleting master {master_id}: {e}")
        await callback.answer(
            f"❌ Ошибка при удалении мастера: {str(e)[:50]}",
            show_alert=True
        )
        return

    from .menu import show_staff_menu
    await show_staff_menu(callback, config, state)