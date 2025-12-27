"""Обработчик команды /start и главное меню"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

logger = logging.getLogger(__name__)

router = Router()


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создание главной клавиатуры"""
    buttons = [
        [KeyboardButton(text="📅 Записаться / Заказать")],
        [KeyboardButton(text="📋 Мои записи")],
        [KeyboardButton(text="❓ Часто задаваемые вопросы")],
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, config: dict):
    """Обработчик команды /start"""
    # Очищаем состояние если было
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


@router.message(F.text.in_(["❓ Часто задаваемые вопросы", "❓ FAQ"]))
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

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = "❓ Часто задаваемые вопросы:\n\nВыберите интересующий вас вопрос:"
    await message.answer(text, reply_markup=keyboard)


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
            answer = "💰 Наши цены:\n"
            for service in services:
                answer += f"• {service['name']} — {service['price']}₽\n"

    # Динамическая подстановка адреса
    if 'адрес' in btn:
        address = config.get('address') or config.get('contacts', {}).get('address')
        if address:
            answer = f"📍 Наш адрес: {address}"

    # Динамический график работы
    if 'час' in btn or 'график' in btn or 'работ' in btn:
        booking = config.get('booking', {})
        work_start = booking.get('work_start', 10)
        work_end = booking.get('work_end', 20)
        answer = f"🕐 Мы работаем:\nЕжедневно: {work_start:02d}:00 - {work_end:02d}:00"

    await callback.message.answer(answer)
    await callback.answer()
