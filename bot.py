# main.py
from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import sqlite3
import json
from utils import edit_product_value
from search import register_search_handlers
from status import register_status_handlers

API_TOKEN = "7050078068:AAHQEzuFqFLzcWX8gEkG3Ltt3fjE8qIJAv0"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Регистрируем обработчики поиска
register_search_handlers(dp)
register_status_handlers(dp)

CATEGORY_PARAMETERS = {
    "Футболка": ["sleeve_length", "width", "shoulder_width", "jacket_length"],
    "Юбка": ["pants_length", "pants_width", "pants_waist"],
    "Брюки": ["pants_length", "pants_width", "pants_waist", "pants_cuff"],
    "Куртка": ["width", "shoulder_width", "jacket_length", "thickness"],
    "Платье": ["shoulder_width", "jacket_length", "pants_length", "width"],
    "Рубашка": ["shoulder_width", "sleeve_length", "width", "jacket_length"],
    "Свитер": ["shoulder_width", "jacket_length", "thickness"],
    "Шуба": ["shoulder_width", "jacket_length", "thickness", "season"],
    "Двойка": ["sleeve_length", "width", "shoulder_width", "jacket_length",
                "pants_length", "pants_width", "pants_waist", "pants_cuff",
                "thickness", "season"]
}

class ProductFSM(StatesGroup):
    waiting_for_photos = State()
    waiting_for_answer = State()
    waiting_for_category = State()
    waiting_for_size_type = State()
    waiting_for_size_list = State()
    waiting_for_size_params = State()

def init_db():
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()

    # Создание таблицы, если не существует
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photos TEXT,
            date TEXT,
            glazhka TEXT,
            model TEXT,
            category TEXT,
            code TEXT,
            sku TEXT,
            size TEXT,
            sizes_data TEXT,
            color TEXT,
            season TEXT,
            description TEXT,
            status TEXT DEFAULT 'На проверке',
            status_comment TEXT
        )
    ''')

    # Добавляем колонку sizes_json, если она отсутствует
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN sizes_json TEXT")
    except sqlite3.OperationalError:
        pass  # колонка уже существует

    conn.commit()
    conn.close()


init_db()

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Добавить товар", "Поиск товар", "Изменить статус проверки")
    await message.answer("Выберите действие:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Добавить товар")
async def add_product(message: types.Message, state: FSMContext):
    await state.update_data(product_data={}, photos=[])
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Готово")
    await message.answer("Отправьте ОДНО или НЕСКОЛЬКО фото как ФАЙЛ (документ). После загрузки нажмите 'Готово'", reply_markup=kb)
    await ProductFSM.waiting_for_photos.set()

@dp.message_handler(state=ProductFSM.waiting_for_photos, content_types=types.ContentTypes.DOCUMENT)
async def handle_photo(message: types.Message, state: FSMContext):
    if message.document.mime_type.startswith("image/"):
        data = await state.get_data()
        photos = data.get("photos", [])
        photos.append(message.document.file_id)
        await state.update_data(photos=photos)
        await message.answer("Фото добавлено!")
    else:
        await message.answer("❗ Отправьте изображение как файл!")

@dp.message_handler(lambda m: m.text == "Готово", state=ProductFSM.waiting_for_photos)
async def finish_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos"):
        await message.answer("Загрузите хотя бы одно фото!")
        return
    await message.answer("Дата:")
    await ProductFSM.waiting_for_answer.set()

questions = [
    ("Дата", "date"),
    ("Глажка исполнитель", "glazhka"),
    ("Модель", "model"),
    ("Код", "code"),
    ("SKU", "sku"),
    ("Цвет", "color"),
    ("Сезон", "season"),
    ("Описание товара", "description")
]

@dp.message_handler(state=ProductFSM.waiting_for_answer)
async def process_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_data = data.get("product_data", {})
    current = len(product_data)
    question = questions[current]
    product_data[question[1]] = message.text.strip()
    await state.update_data(product_data=product_data)

    if current + 1 < len(questions):
        await message.answer(f"{questions[current + 1][0]}:")
    else:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add(*CATEGORY_PARAMETERS.keys())
        await message.answer("Выберите категорию:", reply_markup=kb)
        await ProductFSM.waiting_for_category.set()

@dp.message_handler(state=ProductFSM.waiting_for_category)
async def handle_category(message: types.Message, state: FSMContext):
    cat = message.text.strip()
    if cat not in CATEGORY_PARAMETERS:
        await message.answer("Выберите из кнопок!")
        return
    data = await state.get_data()
    product_data = data.get("product_data", {})
    product_data["category"] = cat
    await state.update_data(product_data=product_data, category_params=CATEGORY_PARAMETERS[cat])
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Стандарт", "Международный", "RUS")
    await message.answer("Выберите тип размера:", reply_markup=kb)
    await ProductFSM.waiting_for_size_type.set()

@dp.message_handler(state=ProductFSM.waiting_for_size_type)
async def handle_size_type(message: types.Message, state: FSMContext):
    t = message.text.strip()
    if t not in ["Стандарт", "Международный", "RUS"]:
        await message.answer("Выберите корректно.")
        return
    await state.update_data(size_type=t)
    if t == "Стандарт":
        await state.update_data(selected_sizes=["Стандарт"], current_size_index=0)
        await ask_next_size_param(message, state)
    else:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)
        sizes = ["XS", "S", "M", "L", "XL", "XXL"] if t == "Международный" else [str(i) for i in range(40, 72, 2)]
        for i in range(0, len(sizes), 3):
            kb.add(*sizes[i:i+3])
        kb.add("Готово")
        await state.update_data(temp_size_selection=[])
        await message.answer("Выберите размеры:", reply_markup=kb)
        await ProductFSM.waiting_for_size_list.set()

@dp.message_handler(state=ProductFSM.waiting_for_size_list)
async def handle_size_selection(message: types.Message, state: FSMContext):
    size = message.text.strip()
    data = await state.get_data()
    selected = data.get("temp_size_selection", [])
    if size == "Готово":
        if not selected:
            await message.answer("Выберите хотя бы один!")
            return
        await state.update_data(selected_sizes=selected, current_size_index=0, sizes_data={})
        await ask_next_size_param(message, state)
        return
    if size in selected:
        await message.answer("Уже выбрано.")
    else:
        selected.append(size)
        await state.update_data(temp_size_selection=selected)
        await message.answer(f"Добавлен: {size}")

async def ask_next_size_param(message, state):
    data = await state.get_data()
    index = data.get("current_param_index", 0)
    category_params = data.get("category_params", [])
    current_size_index = data.get("current_size_index", 0)
    selected_sizes = data.get("selected_sizes", [])

    if current_size_index >= len(selected_sizes):
        await message.answer("\u2705 Все параметры введены. Сохраняем товар...")
        await save_product(message, state)
        return

    if index >= len(category_params):
        sizes_data = data.get("sizes_data", {})
        label = selected_sizes[current_size_index]
        sizes_data[label] = data.get("current_size_data", {})
        await state.update_data(
            sizes_data=sizes_data,
            current_size_index=current_size_index + 1,
            current_param_index=0,
            current_size_data={}
        )
        new_data = await state.get_data()
        if new_data["current_size_index"] >= len(new_data["selected_sizes"]):
            await message.answer("\u2705 Все размеры завершены. Показываем итог...")
            await save_product(message, state)
        else:
            await ask_next_size_param(message, state)
        return

    label = selected_sizes[current_size_index]
    param_key = category_params[index]
    param_label = {
        "sleeve_length": "Длина рукава",
        "width": "Ширина",
        "shoulder_width": "Плечи",
        "jacket_length": "Длина изделия",
        "pants_length": "Длина низа",
        "pants_width": "Ширина низа",
        "pants_waist": "Талия",
        "pants_cuff": "Манжет",
        "thickness": "Толщина",
        "season": "Сезон"
    }.get(param_key, param_key)
    await message.answer(f"\U0001F522 Ввод параметров для {label}\n{param_label}:")
    await ProductFSM.waiting_for_size_params.set()

@dp.message_handler(state=ProductFSM.waiting_for_size_params)
async def handle_size_param_input(message: types.Message, state: FSMContext):
    value = message.text.strip()
    data = await state.get_data()
    index = data.get("current_param_index", 0)
    param_key = data["category_params"][index]
    size_data = data.get("current_size_data", {})
    size_data[param_key] = value
    await state.update_data(current_size_data=size_data, current_param_index=index+1)
    await ask_next_size_param(message, state)

async def save_product(message, state):
    data = await state.get_data()
    product_data = data.get("product_data", {})
    product_data["size"] = ", ".join(data.get("selected_sizes", []))
    product_data["sizes_data"] = json.dumps(data.get("sizes_data", {}), ensure_ascii=False)
    photos = data.get("photos", [])
    fields = list(product_data.keys()) + ["photos", "status", "status_comment"]
    values = list(product_data.values()) + ["","На проверке", ""]
    values[fields.index("photos")] = ",".join(photos)

    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    try:
        cursor.execute(f"INSERT INTO products ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", values)
        conn.commit()
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения в БД: {e}")
    finally:
        conn.close()

    await message.answer("🖼 Отправка фото...")
    if photos:
        for pid in photos[:10]:
            try:
                await bot.send_document(message.chat.id, pid)
            except Exception as e:
                await message.answer(f"❌ Ошибка при отправке документа: {e}")
    else:
        await message.answer("❗ Нет фото для отправки")

    # Словарь русских меток
    label_map = {
        "date": "Дата",
        "glazhka": "Глажка",
        "model": "Модель",
        "code": "Код",
        "sku": "SKU",
        "color": "Цвет",
        "season": "Сезон",
        "description": "Описание",
        "category": "Категория",
        "size": "Размеры",
        "shoulder_width": "Плечи",
        "jacket_length": "Длина изделия",
        "sleeve_length": "Длина рукава",
        "pants_length": "Длина низа",
        "pants_width": "Ширина низа",
        "pants_waist": "Талия",
        "pants_cuff": "Манжет",
        "thickness": "Толщина",
        "width": "Ширина"
    }

    summary = f"\U0001F6CD <b>Карточка товара</b>\n"
    for k, v in product_data.items():
        if k not in ["sizes_data", "photos"]:
            label = label_map.get(k, k)
            summary += f"<b>{label}</b>: {v}\n"

    sizes_data = json.loads(product_data.get("sizes_data", "{}"))
    if sizes_data:
        for size, params in sizes_data.items():
            summary += f"\n<b>{size}</b>:\n"
            for p, val in params.items():
                param_label = label_map.get(p, p)
                summary += f"{param_label}: {val}\n"
    else:
        summary += "\n(Нет данных по размерам)"

    await message.answer("📄 Итоговое сообщение сформировано.")
    try:
        await message.answer(summary, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке итогового текста: {e}")
        await message.answer(summary)

    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)