from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS
from db import (is_admin, add_slot, delete_slot, list_slots,
                get_slot, slot_attendees, count_bookings, 
                update_max_places, remove_user_from_slot)
from keyboards import admin_menu, main_menu, slots_list, admin_attendees_kb, format_date
from schedule_template import TEMPLATE

router = Router()

class AddSlot(StatesGroup):
    waiting_date = State()
    waiting_time = State()
    waiting_title = State()
    waiting_max = State()

def admin_only(msg: Message) -> bool:
    return msg.from_user.id in ADMIN_IDS or is_admin(msg.from_user.id)

async def guard(msg: Message) -> bool:
    if not admin_only(msg):
        await msg.answer("⛔ Только для тренера")
        return False
    return True

@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not admin_only(msg): return
    await msg.answer("⚙️ Админка:", reply_markup=admin_menu())

@router.message(F.text == "⚙️ Админка")
async def btn_admin(msg: Message):
    if not admin_only(msg): return
    await msg.answer("⚙️ Админка:", reply_markup=admin_menu())

@router.message(F.text == "⬅️ В главное меню")
async def back(msg: Message):
    await msg.answer("Главное меню", reply_markup=main_menu(admin_only(msg)))

@router.message(F.text == "🗓 Создать расписание на неделю")
async def generate_week(msg: Message):
    if not await guard(msg): return
    today = datetime.now().date()
    days_ahead = 0 - today.weekday() 
    if days_ahead <= 0: days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    added_count = 0
    for day_offset, slots in TEMPLATE.items():
        current_date = next_monday + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        for time_str, title in slots:
            try:
                add_slot(date_str, time_str, title, 7)
                added_count += 1
            except Exception: pass 
    await msg.answer(f"✅ Создано тренировок: {added_count}", reply_markup=admin_menu())

# --- РУЧНОЕ ДОБАВЛЕНИЕ ---
@router.message(F.text == "➕ Добавить слот")
async def add_slot_start(msg: Message, state: FSMContext):
    if not await guard(msg): return
    await state.set_state(AddSlot.waiting_date)
    await msg.answer("Введи дату в формате ГГГГ-ММ-ДД (например 2026-11-15):")

@router.message(AddSlot.waiting_date, F.text.regexp(r"^\d{4}-\d{2}-\d{2}$"))
async def add_slot_date(msg: Message, state: FSMContext):
    await state.update_data(date=msg.text)
    await state.set_state(AddSlot.waiting_time)
    await msg.answer("Введи время в формате ЧЧ:ММ (например 18:00):")

@router.message(AddSlot.waiting_date)
async def add_slot_date_bad(msg: Message):
    await msg.answer("Формат неверный. Пример: 2026-11-15")

@router.message(AddSlot.waiting_time, F.text.regexp(r"^\d{2}:\d{2}$"))
async def add_slot_time(msg: Message, state: FSMContext):
    await state.update_data(time=msg.text)
    await state.set_state(AddSlot.waiting_title)
    await msg.answer("Введи название тренировки (например: Step, Силовая):")

@router.message(AddSlot.waiting_time)
async def add_slot_time_bad(msg: Message):
    await msg.answer("Формат неверный. Пример: 18:00")

@router.message(AddSlot.waiting_title)
async def add_slot_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text)
    await state.set_state(AddSlot.waiting_max)
    await msg.answer("Сколько мест? (по умолчанию 7 — просто отправь 7):")

@router.message(AddSlot.waiting_max, F.text.regexp(r"^\d+$"))
async def add_slot_max(msg: Message, state: FSMContext):
    data = await state.get_data()
    max_places = int(msg.text)
    try:
        add_slot(data["date"], data["time"], data["title"], max_places)
        await msg.answer(f"✅ Слот {data['date']} {data['time']} ({data['title']}) добавлен", reply_markup=admin_menu())
    except Exception as e:
        await msg.answer(f"⚠️ Ошибка: {e}", reply_markup=admin_menu())
    await state.clear()

@router.message(AddSlot.waiting_max)
async def add_slot_max_bad(msg: Message):
    await msg.answer("Нужно ввести число. Пример: 7")

# --- УДАЛЕНИЕ СЛОТА ---
@router.message(F.text == "🗑 Удалить слот")
async def del_slot_list(msg: Message):
    if not await guard(msg): return
    slots = list_slots()
    if not slots:
        await msg.answer("Слотов нет")
        return
    await msg.answer("Выбери слот для удаления:", reply_markup=slots_list(slots, action_prefix="del"))

@router.callback_query(F.data.startswith("del:"))
async def on_del_slot(cb: CallbackQuery):
    if not admin_only(cb.message): return
    slot_id = int(cb.data.split(":")[1])
    delete_slot(slot_id)
    await cb.answer("Удалено")
    await cb.message.edit_text("🗑 Слот удалён")

# --- ПРОСМОТР И УПРАВЛЕНИЕ ЗАПИСЯМИ ---
@router.message(F.text == "👥 Записи на слот")
async def attendees_list(msg: Message):
    if not await guard(msg): return
    slots = list_slots()
    if not slots:
        await msg.answer("Слотов нет")
        return
    await msg.answer("Выбери слот для просмотра записей:", reply_markup=slots_list(slots, action_prefix="att"))

async def render_attendees(cb: CallbackQuery, slot_id: int):
    slot = get_slot(slot_id)
    people = slot_attendees(slot_id)
    pretty_date = format_date(slot['date'])
    
    header = f"👥 {pretty_date} в {slot['time']} ({slot['title']})\n"
    header += f"Записано: {len(people)} / {slot['max_places']} мест\n\n"
    
    if not people:
        text = header + "Пока никто не записан."
    else:
        text = header + "\n".join(
            f"{i}. {p['full_name']} (@{p['username'] or '—'})"
            for i, p in enumerate(people, 1)
        )
    
    await cb.message.edit_text(text, reply_markup=admin_attendees_kb(slot_id, people))

@router.callback_query(F.data.startswith("att:"))
async def on_att(cb: CallbackQuery):
    if not admin_only(cb.message): return
    slot_id = int(cb.data.split(":")[1])
    await render_attendees(cb, slot_id)
    await cb.answer()

@router.callback_query(F.data.startswith("plus_place:"))
async def on_plus_place(cb: CallbackQuery):
    slot_id = int(cb.data.split(":")[1])
    slot = get_slot(slot_id)
    update_max_places(slot_id, slot['max_places'] + 1)
    await render_attendees(cb, slot_id)
    await cb.answer("Место добавлено")

@router.callback_query(F.data.startswith("minus_place:"))
async def on_minus_place(cb: CallbackQuery):
    slot_id = int(cb.data.split(":")[1])
    slot = get_slot(slot_id)
    if count_bookings(slot_id) >= slot['max_places']:
        await cb.answer("❌ Нельзя убрать место: все заняты!", show_alert=True)
        return
    if slot['max_places'] > 1:
        update_max_places(slot_id, slot['max_places'] - 1)
        await render_attendees(cb, slot_id)
        await cb.answer("Место убрано")
    else:
        await cb.answer("Минимум 1 место", show_alert=True)

@router.callback_query(F.data.startswith("kick:"))
async def on_kick(cb: CallbackQuery):
    _, slot_id, user_id = cb.data.split(":")
    slot_id, user_id = int(slot_id), int(user_id)
    
    if remove_user_from_slot(slot_id, user_id):
        await cb.answer("Клиент убран")
        await render_attendees(cb, slot_id)
    else:
        await cb.answer("Ошибка: клиент не найден", show_alert=True)

@router.callback_query(F.data == "back_to_att_list")
async def on_back_to_list(cb: CallbackQuery):
    slots = list_slots()
    await cb.message.edit_text("Выбери слот для просмотра записей:", reply_markup=slots_list(slots, action_prefix="att"))
    await cb.answer()