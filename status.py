from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import sqlite3

class StatusFSM(StatesGroup):
    waiting_for_reason = State()

def register_status_handlers(dp):
    @dp.message_handler(lambda m: m.text == "Изменить статус проверки")
    async def change_status_start(message: types.Message, state: FSMContext):
        await message.answer("Введите КОД товара, чтобы изменить его статус:")
        await state.set_state("waiting_for_code")

    @dp.message_handler(state="waiting_for_code")
    async def get_product_by_code(message: types.Message, state: FSMContext):
        if not message.text or not message.text.strip():
            await message.answer("❗ Код товара не может быть пустым.")
            return

        code = message.text.strip()
        conn = sqlite3.connect("db.sqlite")
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, model, category, code, status FROM products WHERE code = ?", (code,))
        except Exception as e:
            await message.answer(f"❌ Ошибка при обращении к базе данных: {str(e)}")
            conn.close()
            await state.finish()
            return

        prod = cursor.fetchone()
        conn.close()

        if not prod:
            await message.answer("Товар с таким кодом не найден.")
            await state.finish()
            return

        msg = (
            f"ID: {prod[0]}\n"
            f"Модель: {prod[1]}\n"
            f"Категория: {prod[2]}\n"
            f"Код: {prod[3]}\n"
            f"Статус: {prod[4]}"
        )

        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("Увидеть полный данные", callback_data=f"show_{prod[0]}"),
            InlineKeyboardButton("Изменить данные", callback_data=f"edit_{prod[0]}")
        )
        kb.add(
            InlineKeyboardButton("Подтвердить проверку", callback_data=f"verify_{prod[0]}"),
            InlineKeyboardButton("Не подтверждён", callback_data=f"unverify_{prod[0]}")
        )
        await message.answer(msg, reply_markup=kb)
        await state.finish()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith('verify_'))
    async def verify_product(call: types.CallbackQuery):
        prod_id = call.data.split('_')[1]
        conn = sqlite3.connect("db.sqlite")
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET status = ?, status_comment = ? WHERE id = ?", ("Проверен", "", prod_id))
        conn.commit()
        conn.close()
        await call.message.answer("✅ Статус товара успешно изменён на: Проверен")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith('unverify_'))
    async def unverify_product(call: types.CallbackQuery, state: FSMContext):
        prod_id = call.data.split('_')[1]
        await state.update_data(prod_id=prod_id)
        await call.message.answer("Пожалуйста, напишите причину возврата товара на проверку:")
        await StatusFSM.waiting_for_reason.set()
        await call.answer()

    @dp.message_handler(state=StatusFSM.waiting_for_reason)
    async def save_reason(message: types.Message, state: FSMContext):
        data = await state.get_data()
        prod_id = data.get("prod_id")
        reason = message.text

        conn = sqlite3.connect("db.sqlite")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET status = ?, status_comment = ? WHERE id = ?",
            ("На проверке", reason, prod_id)
        )
        conn.commit()
        conn.close()

        await message.answer(f"❌ Статус товара изменён на: На проверке\nПричина: {reason}")
        await state.finish()
