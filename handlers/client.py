from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS
from db import (upsert_user, is_admin, list_slots, book, unbook,
                user_bookings, get_slot, count_bookings)
from keyboards import main_menu, slots_list, my_bookings_kb, format_date

router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    upsert_user(msg.from_user.id, msg.from_user.username, msg.from_user.full_name)
    admin = is_admin(msg.from_user.id) or msg.from_user.id in ADMIN_IDS
    await msg.answer(f"Привет, {msg.from_user.first_name}! 👋\nВыбери действие:",
                     reply_markup=main_menu(admin))

@router.message(F.text == "📅 Записаться")
async def show_slots(msg: Message):
    slots = list_slots()
    if not slots:
        await msg.answer("Пока нет доступных тренировок 🤷")
        return
    await msg.answer("Выбери тренировку:", reply_markup=slots_list(slots, action_prefix="book"))

@router.callback_query(F.data.startswith("book:"))
async def on_book(cb: CallbackQuery):
    slot_id = int(cb.data.split(":")[1])
    ok, reason = book(slot_id, cb.from_user.id)
    if ok:
        slot = get_slot(slot_id)
        pretty_date = format_date(slot['date'])
        await cb.answer("✅ Ты записан!")
        await cb.message.edit_text(
            f"✅ Записал(а) на {pretty_date} в {slot['time']} ({slot['title']})\n"
            f"Свободно: {slot['max_places'] - count_bookings(slot_id)}"
        )
    else:
        await cb.answer(f"❌ {reason}", show_alert=True)

@router.message(F.text == "📊 Расписание")
async def show_schedule(msg: Message):
    slots = list_slots()
    if not slots:
        await msg.answer("Расписание пусто")
        return
    
    grouped = {}
    for s in slots:
        if s['date'] not in grouped:
            grouped[s['date']] = []
        grouped[s['date']].append(s)
        
    text = "📊 Расписание тренировок:\n\n"
    for date, day_slots in grouped.items():
        text += f"🗓 {format_date(date).upper()}\n"
        for s in day_slots:
            left = s["max_places"] - s["booked"]
            status = "🟢" if left > 0 else "🔴"
            text += f"{status} {s['time']} — {s['title']} (свободно: {left})\n"
        text += "━━━━━━━━━━━━━━\n"
        
    await msg.answer(text)

@router.message(F.text == "❌ Мои записи")
async def my_records(msg: Message):
    bkgs = user_bookings(msg.from_user.id)
    if not bkgs:
        await msg.answer("У тебя нет активных записей")
        return
    await msg.answer("Твои записи (нажми, чтобы отменить):", reply_markup=my_bookings_kb(bkgs))

@router.callback_query(F.data.startswith("unbook:"))
async def on_unbook(cb: CallbackQuery):
    slot_id = int(cb.data.split(":")[1])
    if unbook(slot_id, cb.from_user.id):
        await cb.answer("❌ Отменено")
        await cb.message.edit_text("Запись отменена")
    else:
        await cb.answer("Запись не найдена", show_alert=True)