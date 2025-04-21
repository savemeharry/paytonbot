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
async def cmd_start(message: types.Message):
    """Handle /start command"""
    logger.info(f"ENTERING cmd_start for user {message.from_user.id}")
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Get session factory from dispatcher's data
    session_factory = message.bot.get("session_factory")
    logger.info(f"User {user_id}: Got session_factory: {session_factory}")
    
    if not session_factory:
        logger.error(f"User {user_id}: session_factory not found in bot context!")
        await message.answer("Произошла внутренняя ошибка конфигурации. Пожалуйста, попробуйте позже.")
        return

    try:
        logger.info(f"User {user_id}: Attempting to get DB session...")
        async with get_session(session_factory) as session:
            logger.info(f"User {user_id}: DB session obtained: {session}")
            # Get or create user
            logger.info(f"User {user_id}: Getting or creating user...")
            user = await get_or_create_user(
                session, 
                user_id, 
                username, 
                first_name, 
                last_name
            )
            logger.info(f"User {user_id}: User object: {user}")
            
            # Get active channels
            logger.info(f"User {user_id}: Getting active channels...")
            channels = await get_active_channels(session)
            logger.info(f"User {user_id}: Active channels: {channels}")
            
            # Get user's active subscriptions
            logger.info(f"User {user_id}: Getting user subscriptions...")
            subscriptions = await get_user_subscriptions(session, user_id)
            logger.info(f"User {user_id}: User subscriptions: {subscriptions}")
            
            logger.info(f"User {user_id}: Formatting message...")
            # Generate welcome message based on subscription status
            welcome_text = f"👋 {hbold('Добро пожаловать')}, {user.first_name or 'пользователь'}!\n\n"
            
            if subscriptions:
                welcome_text += f"{hbold('Ваши активные подписки:')}\n"
                for sub in subscriptions:
                    welcome_text += f"📌 {sub.channel.name} - до {sub.end_date.strftime('%d.%m.%Y %H:%M')}\n"
                welcome_text += "\nВы можете продлить текущие подписки или оформить новые:"
            else:
                welcome_text += "У вас пока нет активных подписок. Выберите канал для подписки:"
            
            # Create inline keyboard with channels
            keyboard = InlineKeyboardMarkup(row_width=1)
            
            if channels:
                for channel in channels:
                    keyboard.add(
                        InlineKeyboardButton(
                            text=f"📺 {channel.name}", 
                            callback_data=f"channel:{channel.id}"
                        )
                    )
            else:
                welcome_text += "\n\n❌ В данный момент нет доступных каналов для подписки."
            
            # Add help button
            keyboard.add(
                InlineKeyboardButton(
                    text="ℹ️ Помощь",
                    callback_data="help"
                )
            )
            
            # Send welcome message with keyboard
            logger.info(f"User {user_id}: Sending message...")
            await message.answer(
                welcome_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"User {user_id}: Message sent successfully.")
    except Exception as e:
        logger.error(f"User {user_id}: Error in cmd_start: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")
        except Exception as send_error:
             logger.error(f"User {user_id}: Failed to send error message: {send_error}", exc_info=True)
    finally:
        logger.info(f"EXITING cmd_start for user {user_id}")

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
    dp.register_message_handler(cmd_start, CommandStart())
    dp.register_message_handler(cmd_help, Command("help"))
    dp.register_message_handler(cmd_my_subscriptions, Command("mysubscriptions"))
    
    dp.register_callback_query_handler(callback_back_to_start, lambda c: c.data == "back_to_start")
    dp.register_callback_query_handler(callback_help, lambda c: c.data == "help") 