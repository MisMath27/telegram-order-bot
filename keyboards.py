from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню для пользователя
def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Создать заказ", callback_data="new_order")],
            [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
        ]
    )

# Главное меню для админа
def admin_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Все заказы", callback_data="admin_orders")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
        ]
    )

# Кнопка для отправки номера
def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Кнопки для создания заказа
def order_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📎 Прикрепить файл")],
            [KeyboardButton(text="⏭ Пропустить")]
        ],
        resize_keyboard=True
    )

# Кнопки для статусов заказа (админка)
def order_status_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🆕 Новый", callback_data=f"status_{order_id}_new"),
                InlineKeyboardButton(text="🔄 В работе", callback_data=f"status_{order_id}_in_progress")
            ],
            [
                InlineKeyboardButton(text="✅ Готов", callback_data=f"status_{order_id}_completed"),
                InlineKeyboardButton(text="❌ Отменён", callback_data=f"status_{order_id}_cancelled")
            ],
            [InlineKeyboardButton(text="💬 Комментарий", callback_data=f"comment_{order_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_orders")]
        ]
    )

# Кнопки для списка заказов (админка)
def admin_orders_keyboard(orders, page=0):
    buttons = []
    for order in orders:
        status_emoji = {
            'new': '🆕',
            'in_progress': '🔄',
            'completed': '✅',
            'cancelled': '❌'
        }.get(order['status'], '📝')
        
        client_name = order.get('first_name', 'Неизвестный')
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {order['order_number']} - {client_name}",
                callback_data=f"view_order_{order['order_id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Кнопки для отправки сообщения клиенту
def message_to_client_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📨 Отправить сообщение", callback_data=f"send_msg_{order_id}")],
            [InlineKeyboardButton(text="📎 Отправить файл", callback_data=f"send_file_{order_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"view_order_{order_id}")]
        ]
    )