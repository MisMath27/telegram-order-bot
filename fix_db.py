import aiosqlite
import asyncio

async def fix_database():
    """Добавление отсутствующих колонок в базу данных"""
    async with aiosqlite.connect("orders.db") as db:
        # Проверяем, есть ли колонка admin_comment
        cursor = await db.execute("PRAGMA table_info(orders)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print("📊 Текущие колонки в таблице orders:", column_names)
        
        if 'admin_comment' not in column_names:
            try:
                await db.execute("ALTER TABLE orders ADD COLUMN admin_comment TEXT")
                print("✅ Добавлена колонка admin_comment")
            except Exception as e:
                print(f"❌ Ошибка при добавлении admin_comment: {e}")
        else:
            print("ℹ️ Колонка admin_comment уже существует")
        
        if 'file_name' not in column_names:
            try:
                await db.execute("ALTER TABLE orders ADD COLUMN file_name TEXT")
                print("✅ Добавлена колонка file_name")
            except Exception as e:
                print(f"❌ Ошибка при добавлении file_name: {e}")
        
        if 'file_path' not in column_names:
            try:
                await db.execute("ALTER TABLE orders ADD COLUMN file_path TEXT")
                print("✅ Добавлена колонка file_path")
            except Exception as e:
                print(f"❌ Ошибка при добавлении file_path: {e}")
        
        await db.commit()
        
        # Проверяем результат
        cursor = await db.execute("PRAGMA table_info(orders)")
        columns = await cursor.fetchall()
        print("✅ Колонки после обновления:", [col[1] for col in columns])

asyncio.run(fix_database())
print("✅ База данных обновлена")