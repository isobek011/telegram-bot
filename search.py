from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

class SearchFSM(StatesGroup):
    waiting_for_query = State()

class EditProductFSM(StatesGroup):
    waiting_for_field = State()
    waiting_for_value = State()

def register_search_handlers(dp):
    # Поиск товаров
    @dp.message_handler(lambda m: m.text == "Поиск товар")
    async def search_start(message: types.Message):
        await message.answer("Введите название, код или часть названия товара для поиска:")
        await SearchFSM.waiting_for_query.set()

    @dp.message_handler(state=SearchFSM.waiting_for_query)
    async def search_product(message: types.Message, state: FSMContext):
        query = message.text.lower()
        conn = sqlite3.connect("db.sqlite")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, model, category, code, sku, size, color, status
            FROM products
            WHERE LOWER(model) LIKE ?
               OR LOWER(code) LIKE ?
               OR LOWER(sku) LIKE ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        results = cursor.fetchall()
        conn.close()

        if results:
            for prod in results:
                msg = (
                    f"ID: {prod[0]}\n"
                    f"Модель: {prod[1]}\n"
                    f"Категория: {prod[2]}\n"
                    f"Код: {prod[3]}\n"
                    f"SKU: {prod[4]}\n"
                    f"Размер: {prod[5]}\n"
                    f"Цвет: {prod[6]}\n"
                    f"Статус: {prod[7]}"
                )
                kb = InlineKeyboardMarkup()
                kb.add(
                    InlineKeyboardButton("Увидеть полный данные", callback_data=f"show_{prod[0]}"),
                    InlineKeyboardButton("Изменить данные", callback_data=f"edit_{prod[0]}")
                )
                await message.answer(msg, reply_markup=kb)
        else:
            await message.answer("Ничего не найдено.")
        await state.finish()

    # Обработка кнопки "Увидеть полный данные"
    @dp.callback_query_handler(lambda c: c.data and c.data.startswith('show_'))
    async def show_full_product(call: types.CallbackQuery):
        try:
            prod_id = call.data.split('_')[1]
            conn = sqlite3.connect("db.sqlite")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE id=?", (prod_id,))
            prod = cursor.fetchone()
            field_names = [desc[0] for desc in cursor.description]
            conn.close()

            if not prod:
                await call.message.answer("Товар не найден.")
                await call.answer()
                return

            ru_fields = {
                "id": "ID",
                "photos": "Фото",
                "date": "Дата",
                "glazhka": "Глажка исполнитель",
                "model": "Модель",
                "category": "Категория",
                "code": "Код",
                "sku": "SKU",
                "size": "Размер",
                "color": "Цвет",
                "season": "Сезон",
                "description": "Описание товара",
                "sleeve_length": "Длина рукава",
                "cuff": "Манжет",
                "width": "Ширина одежды",
                "shoulder_width": "Ширина плеч",
                "jacket_length": "Длина кофта",
                "thickness": "Толщина",
                "neck_width": "Ширина шеи",
                "neck_girth": "Обхват шеи",
                "neck_length": "Длина шеи",
                "pants_length": "Длина брюк",
                "pants_width": "Ширина брюк",
                "pants_cuff": "Манжет брюк",
                "pants_waist": "Талия брюк",
                "status": "Статус",
                "status_comment": "Комментарий к статусу"
            }

            msg = ""
            for name, value in zip(field_names, prod):
                if name == "photos":
                    continue
                pretty = ru_fields.get(name, name)
                msg += f"<b>{pretty}:</b> {value}\n"

            photo_file_ids = (prod[field_names.index('photos')] or '').split(',')
            for photo_id in photo_file_ids:
                if photo_id.strip():
                    try:
                        await call.message.answer_document(photo_id)
                    except Exception:
                        pass

            await call.message.answer(msg, parse_mode="HTML")
            await call.answer()
        except Exception:
            await call.message.answer("Ошибка при показе данных.")
            await call.answer()

    # Кнопка "Изменить данные"
    edit_fields = [
        ("Модель", "model"),
        ("Категория", "category"),
        ("Код", "code"),
        ("SKU", "sku"),
        ("Размер", "size"),
        ("Цвет", "color"),
        ("Сезон", "season"),
        ("Описание товара", "description"),
        ("Длина рукава", "sleeve_length"),
        ("Манжет", "cuff"),
        ("Ширина одежды", "width"),
        ("Ширина плеч", "shoulder_width"),
        ("Длина кофта", "jacket_length"),
        ("Толщина", "thickness"),
        ("Ширина шеи", "neck_width"),
        ("Обхват шеи", "neck_girth"),
        ("Длина шеи", "neck_length"),
        ("Длина брюк", "pants_length"),
        ("Ширина брюк", "pants_width"),
        ("Манжет брюк", "pants_cuff"),
        ("Талия брюк", "pants_waist"),
        ("Глажка исполнитель", "glazhka"),
        ("Дата", "date"),
        ("Статус", "status"),
    ]

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith('edit_'))
    async def edit_product_start(call: types.CallbackQuery, state: FSMContext):
        prod_id = call.data.split('_')[1]
        kb = InlineKeyboardMarkup(row_width=2)
        for ru, key in edit_fields:
            kb.add(InlineKeyboardButton(ru, callback_data=f"editfield_{prod_id}_{key}"))
        await call.message.answer("Какое поле хотите изменить?", reply_markup=kb)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith('editfield_'))
    async def edit_product_field(call: types.CallbackQuery, state: FSMContext):
        _, prod_id, field = call.data.split('_', 2)
        await state.update_data(prod_id=prod_id, field=field)
        await call.message.answer("Введите новое значение:")
        await EditProductFSM.waiting_for_value.set()
        await call.answer()

    @dp.message_handler(state=EditProductFSM.waiting_for_value)
    async def edit_product_value(message: types.Message, state: FSMContext):
        data = await state.get_data()
        prod_id = data.get("prod_id")
        field = data.get("field")
        value = message.text

        conn = sqlite3.connect("db.sqlite")
        cursor = conn.cursor()
        cursor.execute(f"UPDATE products SET {field}=? WHERE id=?", (value, prod_id))
        conn.commit()
        conn.close()

        await message.answer(f"Поле успешно обновлено!\nНовое значение: {value}")
        await state.finish()
