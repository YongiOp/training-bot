from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

WEEKDAYS = {
    0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
    4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}

def format_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return WEEKDAYS[dt.weekday()]

def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📅 Записаться")],
        [KeyboardButton(text="📊 Расписание"), KeyboardButton(text="❌ Мои записи")],
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ Админка")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def slots_list(slots, action_prefix: str = "book") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in slots:
        left = s["max_places"] - s["booked"]
        pretty_date = format_date(s['date'])
        # Для админа показываем, сколько записано
        if action_prefix == "att":
            text = f"{pretty_date} {s['time']} — {s['title']} (записано: {s['booked']}/{s['max_places']})"
        else:
            text = f"{pretty_date} | {s['time']} — {s['title']} ({left} мест)"
            
        b.button(text=text, callback_data=f"{action_prefix}:{s['id']}")
    b.adjust(1)
    return b.as_markup()

def my_bookings_kb(bookings) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for bkg in bookings:
        pretty_date = format_date(bkg['date'])
        b.button(
            text=f"❌ {pretty_date} | {bkg['time']} ({bkg['title']})",
            callback_data=f"unbook:{bkg['slot_id']}"
        )
    b.adjust(1)
    return b.as_markup()

def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗓 Создать расписание на неделю")],
            [KeyboardButton(text="➕ Добавить слот")],
            [KeyboardButton(text="🗑 Удалить слот")],
            [KeyboardButton(text="👥 Записи на слот")],
            [KeyboardButton(text="⬅️ В главное меню")],
        ],
        resize_keyboard=True
    )

def admin_attendees_kb(slot_id: int, people) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    # Кнопки изменения мест
    b.row(
        InlineKeyboardButton(text="➖ Убрать место", callback_data=f"minus_place:{slot_id}"),
        InlineKeyboardButton(text="➕ Добавить место", callback_data=f"plus_place:{slot_id}")
    )
    # Кнопки удаления конкретных людей
    for p in people:
        b.row(InlineKeyboardButton(
            text=f"❌ Убрать {p['full_name']}", 
            callback_data=f"kick:{slot_id}:{p['user_id']}"
        ))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_att_list"))
    b.adjust(1)
    return b.as_markup()