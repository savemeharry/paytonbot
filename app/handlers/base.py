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
    
    # Create a modified message with the correct user_id
    message = callback_query.message
    # Make sure the correct user_id is available
    message.from_user = callback_query.from_user
    
    # Call start command handler with the modified message
    await cmd_start(message)

# Callback handler for help button
async def callback_help(callback_query: types.CallbackQuery):
    """Handle help button"""
    await callback_query.answer()
    
    # Create a modified message with the correct user_id
    message = callback_query.message
    # Make sure the correct user_id is available
    message.from_user = callback_query.from_user
    
    # Call help command handler with the modified message
    await cmd_help(message)

# Make admin command handler
async def cmd_make_admin(message: types.Message):
    """Handle /makeadmin command - make user an admin with password"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_make_admin for user {user_id}")
    
    try:
        # Parse command arguments
        try:
            parts = message.text.split()
            if len(parts) < 2:
                logger.info(f"[DEBUG] makeadmin: Недостаточно аргументов: {message.text}")
                await message.answer(
                    "❌ Ошибка в формате команды.\n"
                    "Формат: /makeadmin ПАРОЛЬ"
                )
                return
            
            password = parts[1]
            logger.info(f"[DEBUG] makeadmin: Получен пароль: {password}")
        except ValueError as e:
            logger.info(f"[DEBUG] makeadmin: Ошибка парсинга: {e}")
            await message.answer(
                "❌ Ошибка в формате команды.\n"
                "Формат: /makeadmin ПАРОЛЬ"
            )
            return
        
        # Check password
        admin_password = "301402503"
        if password != admin_password:
            logger.info(f"[DEBUG] makeadmin: Неверный пароль: {password}")
            await message.answer("❌ Неверный пароль.")
            return
            
        # Create a fresh database connection for this event loop
        import os
        from dotenv import load_dotenv
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text
        
        # Load environment variables if needed
        load_dotenv()
        
        # Get database URL
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
        logger.info(f"[DEBUG] Creating new DB engine for makeadmin with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Get user
            from app.models import User
            query = text("SELECT id FROM users WHERE user_id = :user_id")
            logger.info(f"[DEBUG] makeadmin: Выполняем запрос с user_id={user_id}")
            user_query = await session.execute(query, {"user_id": user_id})
            user_id_db = user_query.scalar()
            logger.info(f"[DEBUG] makeadmin: Получен id из базы: {user_id_db}")
            
            if not user_id_db:
                logger.info(f"[DEBUG] makeadmin: Пользователь не найден в БД")
                await message.answer("❌ Пользователь не найден в базе данных. Сначала используйте команду /start")
                await engine.dispose()
                return
            
            # Update user to admin
            update_query = text("UPDATE users SET is_admin = true WHERE id = :user_id_db")
            logger.info(f"[DEBUG] makeadmin: Обновляем пользователя id={user_id_db}")
            await session.execute(update_query, {"user_id_db": user_id_db})
            await session.commit()
            logger.info(f"[DEBUG] makeadmin: Транзакция завершена успешно")
            
            await message.answer("✅ Вы успешно стали администратором!")
            logger.info(f"[DEBUG] makeadmin: Сообщение отправлено пользователю")
            await engine.dispose()
            logger.info(f"[DEBUG] makeadmin: Соединение с БД закрыто")
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_make_admin: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Make admin command handler
async def cmd_create_user(message: types.Message):
    """Handle /createuser command - create user in database"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    logger.info(f"[DEBUG] cmd_create_user for user {user_id}, @{username}")
    
    try:
        # Create a fresh database connection for this event loop
        import os
        from dotenv import load_dotenv
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text
        
        # Load environment variables if needed
        load_dotenv()
        
        # Get database URL
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
        logger.info(f"[DEBUG] Creating new DB engine for createuser with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user already exists
            from app.models import User
            query = text("SELECT id FROM users WHERE user_id = :user_id")
            logger.info(f"[DEBUG] createuser: Проверяем существование пользователя с user_id={user_id}")
            user_query = await session.execute(query, {"user_id": user_id})
            user_id_db = user_query.scalar()
            
            if user_id_db:
                logger.info(f"[DEBUG] createuser: Пользователь уже существует в БД, id={user_id_db}")
                await message.answer("✅ Пользователь уже существует в базе данных.")
                await engine.dispose()
                return
            
            # Create user
            admin_ids = os.getenv("ADMIN_IDS", "").split(",")
            is_admin = str(user_id) in admin_ids
            
            logger.info(f"[DEBUG] createuser: ADMIN_IDS={admin_ids}, is_admin={is_admin}")
            
            insert_query = text("""
                INSERT INTO users (user_id, username, first_name, last_name, is_admin, created_at, last_active) 
                VALUES (:user_id, :username, :first_name, :last_name, :is_admin, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id
            """)
            
            logger.info(f"[DEBUG] createuser: Создаем пользователя user_id={user_id}, is_admin={is_admin}")
            
            result = await session.execute(
                insert_query, 
                {
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_admin": is_admin
                }
            )
            new_id = result.scalar()
            await session.commit()
            
            logger.info(f"[DEBUG] createuser: Пользователь создан, id={new_id}")
            
            # Force additional admin status
            logger.info(f"[DEBUG] createuser: Устанавливаем права администратора для пользователя")
            update_query = text("UPDATE users SET is_admin = true WHERE id = :user_id_db")
            await session.execute(update_query, {"user_id_db": new_id})
            await session.commit()
            
            logger.info(f"[DEBUG] createuser: Права администратора установлены")
            
            await message.answer("✅ Пользователь успешно создан и получил права администратора!")
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_create_user: {e}", exc_info=True)
        await message.answer(f"Произошла ошибка: {str(e)}")

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
    dp.register_message_handler(cmd_make_admin, Command("makeadmin"))
    logger.info(f"Registered cmd_make_admin for Command('makeadmin') filter.")
    dp.register_message_handler(cmd_create_user, Command("createuser"))
    logger.info(f"Registered cmd_create_user for Command('createuser') filter.")
    
    dp.register_callback_query_handler(callback_back_to_start, lambda c: c.data == "back_to_start")
    logger.info(f"Registered callback_back_to_start.")
    dp.register_callback_query_handler(callback_help, lambda c: c.data == "help") 
    logger.info(f"Registered callback_help.")
    logger.info("Base handlers registration finished.") 