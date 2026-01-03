
import calendar
from datetime import datetime, timedelta

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class SimpleCalendarCallback(CallbackData, prefix="simple_calendar"):
    act: str
    year: int
    month: int
    day: int

class SimpleCalendar:
    async def start_calendar(
        self,
        year: int = datetime.now().year,
        month: int = datetime.now().month
    ) -> InlineKeyboardMarkup:
        
        ignore_callback = SimpleCalendarCallback(act="IGNORE", year=year, month=month, day=0).pack()
        
        # first row - month and year
        inline_kb = [
            [
                InlineKeyboardButton(
                    text="<<",
                    callback_data=SimpleCalendarCallback(act="PREV-YEAR", year=year, month=month, day=0).pack()
                ),
                InlineKeyboardButton(
                    text=f'{calendar.month_name[month]} {str(year)}',
                    callback_data=ignore_callback
                ),
                InlineKeyboardButton(
                    text=">>",
                    callback_data=SimpleCalendarCallback(act="NEXT-YEAR", year=year, month=month, day=0).pack()
                )
            ]
        ]
        
        # second row - week days
        inline_kb.append(
            [InlineKeyboardButton(text=day, callback_data=ignore_callback) for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]]
        )

        # third row - days
        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            inline_kb.append(
                [InlineKeyboardButton(
                    text=str(day) if day != 0 else " ",
                    callback_data=SimpleCalendarCallback(act="DAY", year=year, month=month, day=day).pack()
                ) for day in week]
            )
            
        # fourth row - navigation
        inline_kb.append(
            [
                InlineKeyboardButton(
                    text="<",
                    callback_data=SimpleCalendarCallback(act="PREV-MONTH", year=year, month=month, day=0).pack()
                ),
                InlineKeyboardButton(text=" ", callback_data=ignore_callback),
                InlineKeyboardButton(
                    text=">",
                    callback_data=SimpleCalendarCallback(act="NEXT-MONTH", year=year, month=month, day=0).pack()
                )
            ]
        )

        return InlineKeyboardMarkup(inline_keyboard=inline_kb)

    async def process_selection(self, query, data: SimpleCalendarCallback) -> tuple:
        return_data = (False, None)
        
        if data.act == "IGNORE":
            await query.answer(cache_time=60)
            
        if data.act == "DAY":
            await query.message.delete_reply_markup()
            return_data = True, datetime(data.year, data.month, data.day)
            
        if data.act == "PREV-MONTH":
            prev_date = datetime(data.year, data.month, 1) - timedelta(days=1)
            await query.message.edit_reply_markup(reply_markup=await self.start_calendar(int(prev_date.year), int(prev_date.month)))
        
        if data.act == "NEXT-MONTH":
            next_date = datetime(data.year, data.month, 28) + timedelta(days=4)
            await query.message.edit_reply_markup(reply_markup=await self.start_calendar(int(next_date.year), int(next_date.month)))
            
        if data.act == "PREV-YEAR":
            prev_date = datetime(data.year, data.month, 1) - timedelta(days=365)
            await query.message.edit_reply_markup(reply_markup=await self.start_calendar(int(prev_date.year), int(prev_date.month)))
            
        if data.act == "NEXT-YEAR":
            next_date = datetime(data.year, data.month, 1) + timedelta(days=365)
            await query.message.edit_reply_markup(reply_markup=await self.start_calendar(int(next_date.year), int(next_date.month)))

        return return_data
