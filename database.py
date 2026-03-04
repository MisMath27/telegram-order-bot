import aiosqlite
from datetime import datetime
import random
import string
import os
from pathlib import Path

DATABASE = "orders.db"
UPLOAD_FOLDER = "uploads"  # Папка для сохранения файлов

# Создаем папку для загрузок, если её нет
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE) as db:
        # Таблица пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица заказов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                order_number TEXT UNIQUE,
                description TEXT,
                file_path TEXT,
                file_name TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                admin_comment TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица истории статусов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS order_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                old_status TEXT,
                new_status TEXT,
                changed_by INTEGER,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders (order_id)
            )
        ''')
        
        await db.commit()
        
        # Добавляем админа, если ещё нет
        await add_admin_if_not_exists()
        
    print("✅ База данных обновлена")

async def add_admin_if_not_exists():
    """Добавление админа в базу"""
    async with aiosqlite.connect(DATABASE) as db:
        admin_id = 8385109981  # Ваш Telegram ID
        await db.execute(
            "UPDATE users SET is_admin = 1 WHERE user_id = ?",
            (admin_id,)
        )
        await db.commit()

async def user_exists(user_id):
    """Проверка существования пользователя"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None

async def add_user(user_id, username, first_name, phone):
    """Добавление нового пользователя"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, phone) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, phone)
        )
        await db.commit()

async def is_admin(user_id):
    """Проверка, является ли пользователь админом"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row and row[0] == 1

def generate_order_number():
    """Генерация номера заказа"""
    date = datetime.now().strftime("%Y%m")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"INV-{date}-{random_part}"

async def create_order(user_id, description, file_path=None, file_name=None):
    """Создание нового заказа"""
    order_number = generate_order_number()
    
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(
            """INSERT INTO orders 
               (user_id, order_number, description, file_path, file_name, status) 
               VALUES (?, ?, ?, ?, ?, 'new')""",
            (user_id, order_number, description, file_path, file_name)
        )
        await db.commit()
        
        order_id = cursor.lastrowid
        
        await db.execute(
            "INSERT INTO order_history (order_id, old_status, new_status, changed_by) VALUES (?, ?, ?, ?)",
            (order_id, None, 'new', user_id)
        )
        await db.commit()
        
        return order_number, order_id

async def get_user_orders(user_id):
    """Получение заказов пользователя"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM orders 
               WHERE user_id = ? 
               ORDER BY created_at DESC""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_all_orders(limit=20):
    """Получение всех заказов для админа"""
    try:
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory = aiosqlite.Row
            
            query = """
                SELECT 
                    o.order_id,
                    o.order_number,
                    o.status,
                    o.created_at,
                    o.description,
                    o.file_name,
                    u.first_name,
                    u.username,
                    u.phone
                FROM orders o
                LEFT JOIN users u ON o.user_id = u.user_id
                ORDER BY o.created_at DESC
                LIMIT ?
            """
            
            cursor = await db.execute(query, (limit,))
            rows = await cursor.fetchall()
            
            result = []
            for row in rows:
                order_dict = {
                    'order_id': row['order_id'],
                    'order_number': row['order_number'],
                    'status': row['status'],
                    'created_at': row['created_at'],
                    'description': row['description'],
                    'file_name': row['file_name'],
                    'first_name': row['first_name'] or 'Неизвестный',
                    'username': row['username'] or '',
                    'phone': row['phone'] or ''
                }
                result.append(order_dict)
            
            return result
            
    except Exception as e:
        print(f"❌ Ошибка в get_all_orders: {e}")
        return []

async def get_order_by_id(order_id):
    """Получение заказа по ID - БЕЗОПАСНАЯ ВЕРСИЯ"""
    try:
        async with aiosqlite.connect(DATABASE) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT o.*, u.username, u.first_name, u.phone 
                   FROM orders o
                   LEFT JOIN users u ON o.user_id = u.user_id
                   WHERE o.order_id = ?""",
                (order_id,)
            )
            row = await cursor.fetchone()
            if row:
                # Преобразуем в обычный словарь
                result = dict(row)
                # Убедимся, что все нужные поля есть
                if 'admin_comment' not in result:
                    result['admin_comment'] = None
                if 'file_name' not in result:
                    result['file_name'] = None
                if 'file_path' not in result:
                    result['file_path'] = None
                return result
            else:
                print(f"❌ Заказ с ID {order_id} не найден")
                return None
    except Exception as e:
        print(f"❌ Ошибка в get_order_by_id: {e}")
        return None

async def update_order_status(order_id, new_status, changed_by):
    """Обновление статуса заказа"""
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,))
        row = await cursor.fetchone()
        old_status = row[0] if row else None
        
        await db.execute(
            """UPDATE orders 
               SET status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE order_id = ?""",
            (new_status, order_id)
        )
        
        await db.execute(
            "INSERT INTO order_history (order_id, old_status, new_status, changed_by) VALUES (?, ?, ?, ?)",
            (order_id, old_status, new_status, changed_by)
        )
        
        if new_status == 'completed':
            await db.execute(
                "UPDATE orders SET completed_at = CURRENT_TIMESTAMP WHERE order_id = ?",
                (order_id,)
            )
        
        await db.commit()

async def save_uploaded_file(file_id, file_name, bot):
    """Сохранение загруженного файла"""
    file = await bot.get_file(file_id)
    file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{file_name}")
    await bot.download_file(file.file_path, file_path)
    return file_path