import aiosqlite
import asyncio

async def check():
    print("🔍 Проверяем базу данных orders.db...")
    
    try:
        async with aiosqlite.connect("orders.db") as db:
            # Проверяем таблицы
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = await cursor.fetchall()
            print(f"📊 Таблицы в базе: {[t[0] for t in tables]}")
            
            # Проверяем пользователей
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            users_count = await cursor.fetchone()
            print(f"👥 Пользователей: {users_count[0]}")
            
            # Проверяем заказы
            cursor = await db.execute("SELECT COUNT(*) FROM orders")
            orders_count = await cursor.fetchone()
            print(f"📦 Заказов: {orders_count[0]}")
            
            # Показываем все заказы
            if orders_count[0] > 0:
                print("\n📋 Список заказов:")
                cursor = await db.execute("""
                    SELECT o.order_id, o.order_number, o.status, o.created_at, u.first_name 
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.user_id
                    ORDER BY o.created_at DESC
                """)
                orders = await cursor.fetchall()
                for o in orders:
                    print(f"  ID: {o[0]}, Номер: {o[1]}, Статус: {o[2]}, Клиент: {o[4]}")
            else:
                print("❌ Заказов нет!")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")

asyncio.run(check())

input("\nНажмите Enter для выхода...")