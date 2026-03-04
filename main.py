import asyncio
import os
import aiosqlite
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import keyboards as kb

# Загружаем токен
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    print("❌ ОШИБКА: Не найден токен в файле .env!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Состояния для FSM
class OrderStates(StatesGroup):
    description = State()
    file = State()

class AdminStates(StatesGroup):
    waiting_for_comment = State()

class MessageStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_file = State()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    if not await db.user_exists(user_id):
        await message.answer(
            "👋 Добро пожаловать! Для работы с ботом нужно зарегистрироваться.\n"
            "Пожалуйста, отправьте ваш номер телефона:",
            reply_markup=kb.phone_keyboard()
        )
    else:
        if await db.is_admin(user_id):
            await message.answer(
                "👋 Главное меню администратора:",
                reply_markup=kb.admin_main_menu()
            )
        else:
            await message.answer(
                "👋 Главное меню:",
                reply_markup=kb.main_menu()
            )

# Обработка номера телефона
@dp.message(F.contact)
async def handle_contact(message: types.Message):
    user_id = message.from_user.id
    
    await db.add_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        phone=message.contact.phone_number
    )
    
    await message.answer(
        "✅ Регистрация завершена!",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    if await db.is_admin(user_id):
        await message.answer(
            "👋 Главное меню администратора:",
            reply_markup=kb.admin_main_menu()
        )
    else:
        await message.answer(
            "👋 Главное меню:",
            reply_markup=kb.main_menu()
        )

# Создание нового заказа
@dp.callback_query(F.data == "new_order")
async def new_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Опишите, какой чертеж вам нужен:\n"
        "• Что нужно начертить\n"
        "• Требования по ГОСТ\n"
        "• Срочность"
    )
    await state.set_state(OrderStates.description)

@dp.message(OrderStates.description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        "Хотите прикрепить файл (эскиз, референс)?",
        reply_markup=kb.order_keyboard()
    )
    await state.set_state(OrderStates.file)

@dp.message(OrderStates.file, F.document)
async def process_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_path = await db.save_uploaded_file(
        message.document.file_id,
        message.document.file_name,
        bot
    )
    
    order_number, order_id = await db.create_order(
        user_id=message.from_user.id,
        description=data['description'],
        file_path=file_path,
        file_name=message.document.file_name
    )
    
    await message.answer(
        f"✅ **Заказ №{order_number} создан!**\n\n"
        f"Файл прикреплен: {message.document.file_name}\n"
        f"Я свяжусь с вами в ближайшее время.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()
    await notify_admin_new_order(order_number, message.from_user.id, order_id)

@dp.message(OrderStates.file, F.text == "⏭ Пропустить")
async def skip_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_number, order_id = await db.create_order(
        user_id=message.from_user.id,
        description=data['description']
    )
    
    await message.answer(
        f"✅ **Заказ №{order_number} создан!**\n\n"
        f"Я свяжусь с вами в ближайшее время.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()
    await notify_admin_new_order(order_number, message.from_user.id, order_id)

async def notify_admin_new_order(order_number, user_id, order_id):
    try:
        user = await bot.get_chat(user_id)
        await bot.send_message(
            ADMIN_ID,
            f"🔔 **НОВЫЙ ЗАКАЗ!**\n\n"
            f"📋 Номер: {order_number}\n"
            f"👤 Клиент: {user.first_name} (@{user.username})\n"
            f"🆔 ID: {user_id}\n\n"
            f"Подробнее: /order_{order_id}",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"❌ Ошибка уведомления: {e}")

@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: types.CallbackQuery):
    orders = await db.get_user_orders(callback.from_user.id)
    
    if not orders:
        await callback.message.edit_text(
            "📭 У вас пока нет заказов",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]]
            )
        )
        return
    
    text = "📋 **Ваши заказы:**\n\n"
    for order in orders:
        status_emoji = {
            'new': '🆕',
            'in_progress': '🔄',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order['status'], '📝')
        
        text += f"{status_emoji} **{order['order_number']}**\n"
        text += f"Статус: {order['status']}\n"
        text += f"Дата: {order['created_at'][:10]}\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]]
        )
    )

# ==================== АДМИН-ПАНЕЛЬ ====================

@dp.callback_query(F.data == "admin_main")
async def admin_main(callback: types.CallbackQuery):
    if not await db.is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔️ Доступ запрещен")
        return
    
    await callback.message.edit_text(
        "👋 **Панель администратора**\n\n"
        "Выберите раздел:",
        parse_mode="Markdown",
        reply_markup=kb.admin_main_menu()
    )

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: types.CallbackQuery):
    if not await db.is_admin(callback.from_user.id):
        await callback.message.edit_text("⛔️ Доступ запрещен")
        return
    
    orders = await db.get_all_orders(limit=10)
    
    if not orders:
        await callback.message.edit_text(
            "📭 Нет заказов в базе данных",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main")]]
            )
        )
        return
    
    await callback.message.edit_text(
        "📋 **Последние заказы:**",
        parse_mode="Markdown",
        reply_markup=kb.admin_orders_keyboard(orders, page=0)
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not await db.is_admin(callback.from_user.id):
        return
    
    async with aiosqlite.connect(db.DATABASE) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        
        cursor = await conn.execute("SELECT COUNT(*) FROM orders")
        total_orders = (await cursor.fetchone())[0]
        
        cursor = await conn.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        status_stats = await cursor.fetchall()
    
    text = "📊 **Статистика:**\n\n"
    text += f"👥 Всего пользователей: {total_users}\n"
    text += f"📋 Всего заказов: {total_orders}\n\n"
    
    if status_stats:
        text += "**Заказы по статусам:**\n"
        status_names = {
            'new': '🆕 Новые',
            'in_progress': '🔄 В работе',
            'completed': '✅ Готовые',
            'cancelled': '❌ Отмененные'
        }
        for status, count in status_stats:
            name = status_names.get(status, status)
            text += f"{name}: {count}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main")]]
        )
    )

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if not await db.is_admin(callback.from_user.id):
        return
    
    async with aiosqlite.connect(db.DATABASE) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT user_id, username, first_name, phone, registered_at FROM users ORDER BY registered_at DESC LIMIT 10"
        )
        users = await cursor.fetchall()
    
    if not users:
        await callback.message.edit_text("👥 Пользователей пока нет")
        return
    
    text = "👥 **Последние пользователи:**\n\n"
    for user in users:
        text += f"👤 {user['first_name']}"
        if user['username']:
            text += f" (@{user['username']})"
        text += f"\n📱 {user['phone'] or 'не указан'}"
        text += f"\n🆔 {user['user_id']}"
        text += f"\n📅 {user['registered_at'][:10]}\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main")]]
        )
    )

@dp.callback_query(lambda c: c.data.startswith("view_order_"))
async def view_order(callback: types.CallbackQuery):
    if not await db.is_admin(callback.from_user.id):
        return
    
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order_by_id(order_id)
    
    if not order:
        await callback.message.edit_text("❌ Заказ не найден")
        return
    
    status_emoji = {
        'new': '🆕',
        'in_progress': '🔄',
        'completed': '✅',
        'cancelled': '❌'
    }.get(order['status'], '📝')
    
    text = f"**Заказ {status_emoji} {order['order_number']}**\n\n"
    text += f"**Клиент:** {order.get('first_name', 'Неизвестно')}\n"
    text += f"**Телефон:** {order.get('phone', 'Не указан')}\n"
    text += f"**Username:** @{order.get('username', 'Нет')}\n\n"
    text += f"**Описание:**\n{order.get('description', 'Нет описания')}\n\n"
    text += f"**Статус:** {order.get('status', 'new')}\n"
    text += f"**Создан:** {order.get('created_at', 'Неизвестно')}\n"
    
    if order.get('file_name'):
        text += f"\n**Файл:** {order['file_name']}"
    
    if order.get('admin_comment'):
        text += f"\n\n**Комментарий:**\n{order['admin_comment']}"
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    
    await callback.message.answer(
        "⚙️ Управление статусом:",
        reply_markup=kb.order_status_keyboard(order_id)
    )
    
    await callback.message.answer(
        "📨 Связь с клиентом:",
        reply_markup=kb.message_to_client_keyboard(order_id)
    )
    
    if order.get('file_path') and os.path.exists(order['file_path']):
        try:
            await callback.message.answer_document(
                FSInputFile(order['file_path']),
                caption=f"📎 Файл к заказу {order['order_number']}"
            )
        except:
            pass

@dp.callback_query(lambda c: c.data.startswith("status_"))
async def change_status(callback: types.CallbackQuery):
    if not await db.is_admin(callback.from_user.id):
        return
    
    parts = callback.data.split("_")
    order_id = int(parts[1])
    new_status = parts[2]
    
    await db.update_order_status(order_id, new_status, callback.from_user.id)
    
    order = await db.get_order_by_id(order_id)
    if order:
        status_messages = {
            'in_progress': "🔄 Ваш заказ переведен в статус **В работе**",
            'completed': "✅ Ваш заказ **выполнен**! Свяжитесь с исполнителем",
            'cancelled': "❌ Ваш заказ **отменен**"
        }
        
        if new_status in status_messages:
            try:
                await bot.send_message(
                    order['user_id'],
                    f"{status_messages[new_status]}\n\nЗаказ №{order['order_number']}"
                )
            except:
                pass
    
    await callback.answer(f"Статус изменен на {new_status}")

@dp.callback_query(lambda c: c.data.startswith("comment_"))
async def ask_comment(callback: types.CallbackQuery, state: FSMContext):
    if not await db.is_admin(callback.from_user.id):
        return
    
    order_id = int(callback.data.split("_")[1])
    await state.update_data(comment_order_id=order_id)
    await callback.message.edit_text("✏️ Введите комментарий к заказу:")
    await state.set_state(AdminStates.waiting_for_comment)

@dp.message(AdminStates.waiting_for_comment)
async def save_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['comment_order_id']
    
    async with aiosqlite.connect(db.DATABASE) as conn:
        await conn.execute(
            "UPDATE orders SET admin_comment = ? WHERE order_id = ?",
            (message.text, order_id)
        )
        await conn.commit()
    
    await message.answer("✅ Комментарий сохранен")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("send_msg_"))
async def send_message_to_client(callback: types.CallbackQuery, state: FSMContext):
    if not await db.is_admin(callback.from_user.id):
        return
    
    order_id = int(callback.data.split("_")[2])
    await state.update_data(msg_order_id=order_id)
    await callback.message.edit_text("✏️ Введите сообщение для клиента:")
    await state.set_state(MessageStates.waiting_for_message)

@dp.message(MessageStates.waiting_for_message)
async def process_client_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['msg_order_id']
    order = await db.get_order_by_id(order_id)
    
    if not order:
        await message.answer("❌ Заказ не найден")
        await state.clear()
        return
    
    try:
        await bot.send_message(
            order['user_id'],
            f"📨 **Сообщение от администратора по заказу {order['order_number']}:**\n\n{message.text}",
            parse_mode="Markdown"
        )
        await message.answer("✅ Сообщение отправлено клиенту!")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")
    
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("send_file_"))
async def send_file_to_client(callback: types.CallbackQuery, state: FSMContext):
    if not await db.is_admin(callback.from_user.id):
        return
    
    order_id = int(callback.data.split("_")[2])
    await state.update_data(file_order_id=order_id)
    await callback.message.edit_text("📎 Отправьте файл для клиента:")
    await state.set_state(MessageStates.waiting_for_file)

@dp.message(MessageStates.waiting_for_file, F.document)
async def process_client_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['file_order_id']
    order = await db.get_order_by_id(order_id)
    
    if not order:
        await message.answer("❌ Заказ не найден")
        await state.clear()
        return
    
    try:
        await bot.send_document(
            order['user_id'],
            message.document.file_id,
            caption=f"📎 **Файл от администратора по заказу {order['order_number']}**",
            parse_mode="Markdown"
        )
        await message.answer("✅ Файл отправлен клиенту!")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")
    
    await state.clear()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    if await db.is_admin(callback.from_user.id):
        await callback.message.edit_text(
            "👋 Главное меню администратора:",
            reply_markup=kb.admin_main_menu()
        )
    else:
        await callback.message.edit_text(
            "👋 Главное меню:",
            reply_markup=kb.main_menu()
        )

@dp.message(lambda m: m.text and m.text.startswith('/order_'))
async def cmd_order(message: types.Message):
    if not await db.is_admin(message.from_user.id):
        return
    
    try:
        order_id = int(message.text.split('_')[1])
        order = await db.get_order_by_id(order_id)
        
        if order:
            await view_order(
                types.CallbackQuery(
                    id="fake",
                    from_user=message.from_user,
                    message=message,
                    data=f"view_order_{order_id}"
                )
            )
        else:
            await message.answer("❌ Заказ не найден")
    except:
        await message.answer("❌ Неверный формат")

@dp.message(Command("debug"))
async def debug_db(message: types.Message):
    if not await db.is_admin(message.from_user.id):
        return
    
    await message.answer("🔍 Проверяю базу данных...")
    
    try:
        async with aiosqlite.connect(db.DATABASE) as conn:
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            await message.answer(f"📊 Таблицы: {[t[0] for t in tables]}")
            
            cursor = await conn.execute("SELECT COUNT(*) FROM orders")
            count = await cursor.fetchone()
            await message.answer(f"📦 Всего заказов: {count[0]}")
            
            if count[0] > 0:
                cursor = await conn.execute("SELECT order_id, order_number, status FROM orders LIMIT 3")
                orders = await cursor.fetchall()
                text = "📋 Первые заказы:\n"
                for o in orders:
                    text += f"ID: {o[0]}, Номер: {o[1]}, Статус: {o[2]}\n"
                await message.answer(text)
            else:
                await message.answer("❌ Заказов нет!")
                
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    await db.init_db()
    print("🚀 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())