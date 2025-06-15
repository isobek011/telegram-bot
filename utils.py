import sqlite3
import json

def edit_product_value(prod_id: int, field: str, value: str, size: str = None):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()

    # Если обновляем обычное поле (в колонке data)
    if size is None:
        cursor.execute("SELECT data FROM products WHERE id=?", (prod_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Товар не найден")

        data_raw = row[0]
        data = json.loads(data_raw) if data_raw else {}
        data[field] = value
        cursor.execute("UPDATE products SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), prod_id))
        conn.commit()
        conn.close()
        return

    # Обновление параметра размера
    cursor.execute("SELECT sizes_json FROM products WHERE id=?", (prod_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Товар не найден")

    sizes_raw = row[0]
    sizes = json.loads(sizes_raw) if sizes_raw else {}
    if size not in sizes:
        sizes[size] = {}
    sizes[size][field] = value

    cursor.execute("UPDATE products SET sizes_json=? WHERE id=?", (json.dumps(sizes, ensure_ascii=False), prod_id))
    conn.commit()
    conn.close()
