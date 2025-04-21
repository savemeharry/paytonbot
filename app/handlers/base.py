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
        
        # Get the bot instance - check multiple ways
        bot_instance = None
        try:
            # Try to get from message
            bot_instance = message.bot
            logger.info(f"[DEBUG] Got bot from message")
        except Exception as e1:
            try:
                # Try to get current bot
                from aiogram import Bot
                bot_instance = Bot.get_current()
                logger.info(f"[DEBUG] Got bot from current")
            except Exception as e2:
                # Use global bot as last resort
                from webhook import bot as global_bot
                bot_instance = global_bot
                logger.info(f"[DEBUG] Using global bot")
        
        # Log bot data keys if available
        if hasattr(bot_instance, 'data'):
            logger.info(f"[DEBUG] Bot data keys: {list(bot_instance.data.keys())}")
        
        # Send the welcome message
        logger.info(f"[DEBUG] About to send message to user {message.from_user.id}")
        result = await message.answer(
            "Добро пожаловать! Я бот для управления подписками на каналы. Чем могу помочь?", 
            reply_markup=keyboard
        )
        logger.info(f"[DEBUG] Message sent successfully, message_id: {result.message_id}")
        
    except Exception as e:
        error_msg = f"Error in cmd_start: {e}"
        logger.error(error_msg, exc_info=True)
        
        # Try fallback direct message using the API
        try:
            # Import at top level to avoid circular imports
            import requests
            import os
            
            bot_token = os.getenv("BOT_TOKEN")
            send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                'chat_id': message.from_user.id,
                'text': "Произошла ошибка при обработке команды. Попробуйте позже."
            }
            
            response = requests.post(send_url, json=payload)
            logger.info(f"[DEBUG] Fallback message response: {response.status_code} - {response.text}")
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
    logger.info(f"[DEBUG] cmd_my_subscriptions for user {user_id}")
    
    try:
        # Create a fresh database connection for this event loop
        import os
        from dotenv import load_dotenv
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Load environment variables if needed
        load_dotenv()
        
        # Get database URL
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
        logger.info(f"[DEBUG] Creating new DB engine for mysubscriptions with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Use the session factory to get user subscriptions
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
            
            # Send the response
            await message.answer(
                subs_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Clean up resources
            await engine.dispose()
            
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_my_subscriptions: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении ваших подписок. Пожалуйста, попробуйте позже.")

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