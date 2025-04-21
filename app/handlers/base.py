import logging
from datetime import datetime
from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import CommandStart, Command
from aiogram.utils.markdown import hbold

from app.utils.db import get_session
from app.services.user import get_or_create_user
from app.services.channel import get_active_channels
from app.services.subscription import get_user_subscriptions

logger = logging.getLogger(__name__)

# Start command handler
# async def cmd_start(message: types.Message): (КОММЕНТИРУЕМ СТАРЫЙ)
#     """Handle /start command"""
#     logger.info(f"ENTERING cmd_start for user {message.from_user.id}") 
#     user_id = message.from_user.id
#     username = message.from_user.username
# ... (весь остальной код старого cmd_start закомментирован) ...
#     finally:
#         logger.info(f"EXITING cmd_start for user {user_id}")

# ПРОСТОЙ ТЕСТОВЫЙ ОБРАБОТЧИК
async def cmd_start(message: types.Message):
    logger.info(f"SIMPLE cmd_start called for user {message.from_user.id}")
    try:
        # Create keyboard with a simple button
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")
        )
        
        # Log important message info and dispatcher data
        logger.info(f"User ID: {message.from_user.id}, Username: {message.from_user.username}")
        logger.info(f"Bot data keys: {list(message.bot.data.keys() if hasattr(message.bot, 'data') else [])}")
        
        # Send the welcome message
        result = await message.answer(
            "Добро пожаловать! Я бот для управления подписками на каналы. Чем могу помочь?", 
            reply_markup=keyboard
        )
        logger.info(f"Message sent successfully, message_id: {result.message_id}")
        
    except Exception as e:
        error_msg = f"Error in cmd_start: {e}"
        logger.error(error_msg, exc_info=True)
        
        # Try fallback direct message using the API
        try:
            from webhook import send_direct_message
            send_direct_message(
                message.from_user.id, 
                "Произошла ошибка при обработке команды. Попробуйте позже."
            )
            logger.info(f"Sent fallback message to {message.from_user.id}")
        except Exception as fallback_error:
            logger.error(f"Even fallback failed: {fallback_error}", exc_info=True)

# Help command handler
async def cmd_help(message: types.Message):
    """Handle /help command"""
    help_text = (
        f"{hbold('Как пользоваться ботом:')}\n\n"
        f"1️⃣ Выберите канал, на который хотите подписаться\n"
        f"2️⃣ Выберите тариф подписки (неделя, месяц и т.д.)\n"
        f"3️⃣ Оплатите подписку через Telegram Stars\n"
        f"4️⃣ После оплаты вы получите приглашение в приватный канал\n\n"
        f"{hbold('Команды бота:')}\n"
        f"/start - Главное меню\n"
        f"/help - Эта справка\n"
        f"/mysubscriptions - Ваши активные подписки\n\n"
        f"По всем вопросам обращайтесь к администратору."
    )
    
    # Create keyboard
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(
            text="🔙 Вернуться в главное меню",
            callback_data="back_to_start"
        )
    )
    
    await message.answer(
        help_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# My subscriptions command handler
async def cmd_my_subscriptions(message: types.Message):
    """Handle /mysubscriptions command"""
    user_id = message.from_user.id
    session_factory = message.bot.get("session_factory")
    
    async with get_session(session_factory) as session:
        # Get user's active subscriptions
        subscriptions = await get_user_subscriptions(session, user_id)
        
        if subscriptions:
            subs_text = f"{hbold('Ваши активные подписки:')}\n\n"
            for sub in subscriptions:
                end_date = sub.end_date.strftime("%d.%m.%Y %H:%M")
                subs_text += f"📌 {sub.channel.name}\n"
                subs_text += f"📅 Активна до: {end_date}\n"
                subs_text += f"💰 Тариф: {sub.tariff.name}\n\n"
        else:
            subs_text = "У вас нет активных подписок."
        
        # Create keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="refresh_subscriptions"
            )
        )
        keyboard.add(
            InlineKeyboardButton(
                text="🔙 Вернуться в главное меню",
                callback_data="back_to_start"
            )
        )
        
        await message.answer(
            subs_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

# Callback handler for back to start button
async def callback_back_to_start(callback_query: types.CallbackQuery):
    """Handle back to start button"""
    await callback_query.answer()
    
    # Call start command handler with the same message
    await cmd_start(callback_query.message)

# Callback handler for help button
async def callback_help(callback_query: types.CallbackQuery):
    """Handle help button"""
    await callback_query.answer()
    
    # Call help command handler with the same message
    await cmd_help(callback_query.message)

# Register base handlers
def register_base_handlers(dp: Dispatcher):
    """Register all base handlers"""
    logger.info("Registering base handlers...")
    dp.register_message_handler(cmd_start, CommandStart())
    logger.info(f"Registered cmd_start for CommandStart filter.")
    dp.register_message_handler(cmd_help, Command("help"))
    logger.info(f"Registered cmd_help for Command('help') filter.")
    dp.register_message_handler(cmd_my_subscriptions, Command("mysubscriptions"))
    logger.info(f"Registered cmd_my_subscriptions for Command('mysubscriptions') filter.")
    
    dp.register_callback_query_handler(callback_back_to_start, lambda c: c.data == "back_to_start")
    logger.info(f"Registered callback_back_to_start.")
    dp.register_callback_query_handler(callback_help, lambda c: c.data == "help") 
    logger.info(f"Registered callback_help.")
    logger.info("Base handlers registration finished.") 