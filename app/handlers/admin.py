import logging
import re
from datetime import datetime, timedelta
from aiogram import Dispatcher, types
from aiogram.dispatcher.filters import Command
from aiogram.utils.markdown import hbold, hcode
from sqlalchemy import text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.utils.db import get_session
from app.services.user import is_admin
from app.models import User, Channel, Tariff, Subscription

logger = logging.getLogger(__name__)

# Создаем клавиатуру для админ-панели
def get_admin_keyboard():
    """Create keyboard for admin panel"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats"),
        InlineKeyboardButton("📺 Управление каналами", callback_data="admin_channels"),
        InlineKeyboardButton("🔑 Управление подписками", callback_data="admin_subs"),
        InlineKeyboardButton("↩️ Назад в основное меню", callback_data="back_to_start")
    )
    return keyboard

# Создаем клавиатуру для управления каналами
def get_channels_keyboard():
    """Create keyboard for channel management"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить канал", callback_data="add_channel"),
        InlineKeyboardButton("🔄 Вкл/выкл канал", callback_data="toggle_channel"),
        InlineKeyboardButton("➕ Добавить тариф", callback_data="add_tariff"),
        InlineKeyboardButton("↩️ Назад в админ-панель", callback_data="back_to_admin")
    )
    return keyboard

# Создаем клавиатуру для управления подписками
def get_subscriptions_keyboard():
    """Create keyboard for subscription management"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить подписку", callback_data="add_sub"),
        InlineKeyboardButton("➖ Удалить подписку", callback_data="del_sub"),
        InlineKeyboardButton("↩️ Назад в админ-панель", callback_data="back_to_admin")
    )
    return keyboard

# Admin command handler
async def cmd_admin(message: types.Message):
    """Handle /admin command - show admin panel"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_admin for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for admin with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Show admin panel
            admin_text = f"{hbold('Панель администратора:')}\n\nВыберите действие:"
            
            await message.answer(admin_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_admin: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик callback-запросов для админ-панели
async def admin_callback_handler(callback_query: types.CallbackQuery):
    """Handle admin panel callbacks"""
    user_id = callback_query.from_user.id
    callback_data = callback_query.data
    logger.info(f"[DEBUG] admin_callback_handler for user {user_id}, data: {callback_data}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for admin_callback with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await callback_query.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
                
            # Обработка различных callback-запросов
            if callback_data == "admin_stats":
                await process_admin_stats(callback_query, session)
            elif callback_data == "admin_channels":
                await process_admin_channels(callback_query, session)
            elif callback_data == "admin_subs":
                await process_admin_subs(callback_query, session)
            elif callback_data == "back_to_admin":
                admin_text = f"{hbold('Панель администратора:')}\n\nВыберите действие:"
                await callback_query.message.edit_text(admin_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
            elif callback_data == "add_channel":
                await callback_query.message.edit_text(
                    f"{hbold('Добавление канала:')}\n\n"
                    f"Используйте команду:\n"
                    f"/add_channel CHANNEL_ID NAME\n\n"
                    f"Пример: /add_channel -1001234567890 Мой канал", 
                    parse_mode="HTML", 
                    reply_markup=get_channels_keyboard()
                )
            elif callback_data == "toggle_channel":
                # Получаем список каналов для отображения
                channels = await session.execute(
                    text("SELECT id, channel_id, name, is_active FROM channels")
                )
                channels = channels.all()
                
                channels_text = f"{hbold('Управление статусом каналов:')}\n\n"
                if channels:
                    for channel in channels:
                        id, channel_id, name, is_active = channel
                        status = "✅ Активен" if is_active else "❌ Неактивен"
                        channels_text += f"ID: {id} | {name} | {status}\n"
                    
                    channels_text += f"\n{hbold('Для вкл/выкл канала используйте команду:')}\n/toggle_channel ID"
                else:
                    channels_text += "Нет настроенных каналов."
                
                await callback_query.message.edit_text(
                    channels_text, 
                    parse_mode="HTML", 
                    reply_markup=get_channels_keyboard()
                )
            elif callback_data == "add_tariff":
                await callback_query.message.edit_text(
                    f"{hbold('Добавление тарифа:')}\n\n"
                    f"Используйте команду:\n"
                    f"/add_tariff CHANNEL_ID NAME DAYS PRICE\n\n"
                    f"Пример: /add_tariff 1 Месяц 30 1000",
                    parse_mode="HTML", 
                    reply_markup=get_channels_keyboard()
                )
            elif callback_data == "add_sub":
                await callback_query.message.edit_text(
                    f"{hbold('Добавление подписки:')}\n\n"
                    f"Используйте команду:\n"
                    f"/add_sub USER_ID CHANNEL_ID TARIFF_ID\n\n"
                    f"Пример: /add_sub 123456789 1 1",
                    parse_mode="HTML", 
                    reply_markup=get_subscriptions_keyboard()
                )
            elif callback_data == "del_sub":
                await callback_query.message.edit_text(
                    f"{hbold('Удаление подписки:')}\n\n"
                    f"Используйте команду:\n"
                    f"/del_sub SUBSCRIPTION_ID\n\n"
                    f"Пример: /del_sub 5",
                    parse_mode="HTML", 
                    reply_markup=get_subscriptions_keyboard()
                )
            
            await callback_query.answer()
        
        await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in admin_callback_handler: {e}", exc_info=True)
        await callback_query.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик статистики для callback
async def process_admin_stats(callback_query: types.CallbackQuery, session):
    """Process admin_stats callback"""
    try:
        # Check if user is admin
        user_id = callback_query.from_user.id
        if not await is_admin(session, user_id):
            await callback_query.answer("У вас нет прав администратора.")
            return
            
        # Get statistics from database
        stats = {}
        
        # Users count
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        stats['users_total'] = result.scalar() or 0
        
        # Active users (with at least one active subscription)
        result = await session.execute(
            text("""
            SELECT COUNT(DISTINCT user_id) 
            FROM subscriptions 
            WHERE is_active = true
            """)
        )
        stats['users_active'] = result.scalar() or 0
        
        # Channels count
        result = await session.execute(text("SELECT COUNT(*) FROM channels"))
        stats['channels_total'] = result.scalar() or 0
        
        # Active channels
        result = await session.execute(
            text("SELECT COUNT(*) FROM channels WHERE is_active = true")
        )
        stats['channels_active'] = result.scalar() or 0
        
        # Subscriptions count
        result = await session.execute(text("SELECT COUNT(*) FROM subscriptions"))
        stats['subscriptions_total'] = result.scalar() or 0
        
        # Active subscriptions
        result = await session.execute(
            text("SELECT COUNT(*) FROM subscriptions WHERE is_active = true")
        )
        stats['subscriptions_active'] = result.scalar() or 0
        
        # Format message
        stats_text = f"{hbold('Статистика бота')}\n\n"
        
        stats_text += f"👤 {hbold('Пользователи:')}\n"
        stats_text += f"   • Всего: {stats['users_total']}\n"
        if stats['users_total'] > 0:
            stats_text += f"   • Активных: {stats['users_active']} ({round(stats['users_active']/stats['users_total']*100, 1)}% от общего числа)\n\n"
        else:
            stats_text += f"   • Активных: {stats['users_active']} (0% от общего числа)\n\n"
        
        stats_text += f"📺 {hbold('Каналы:')}\n"
        stats_text += f"   • Всего: {stats['channels_total']}\n"
        if stats['channels_total'] > 0:
            stats_text += f"   • Активных: {stats['channels_active']} ({round(stats['channels_active']/stats['channels_total']*100, 1)}% от общего числа)\n\n"
        else:
            stats_text += f"   • Активных: {stats['channels_active']} (0% от общего числа)\n\n"
        
        stats_text += f"🔗 {hbold('Подписки:')}\n"
        stats_text += f"   • Всего: {stats['subscriptions_total']}\n"
        if stats['subscriptions_total'] > 0:
            stats_text += f"   • Активных: {stats['subscriptions_active']} ({round(stats['subscriptions_active']/stats['subscriptions_total']*100, 1)}% от общего числа)\n\n"
        else:
            stats_text += f"   • Активных: {stats['subscriptions_active']} (0% от общего числа)\n\n"
        
        await callback_query.message.edit_text(
            stats_text, 
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"[DEBUG] Error in process_admin_stats: {e}", exc_info=True)
        await callback_query.message.edit_text(
            "Произошла ошибка при получении статистики.",
            reply_markup=get_admin_keyboard()
        )

# Обработчик каналов для callback
async def process_admin_channels(callback_query: types.CallbackQuery, session):
    """Process admin_channels callback"""
    try:
        # Check if user is admin
        user_id = callback_query.from_user.id
        if not await is_admin(session, user_id):
            await callback_query.answer("У вас нет прав администратора.")
            return
            
        # Get all channels
        channels = await session.execute(
            text("SELECT id, channel_id, name, is_active FROM channels")
        )
        channels = channels.all()
        
        channels_text = f"{hbold('Список каналов:')}\n\n"
        
        if not channels:
            channels_text += "Нет настроенных каналов.\n\n"
        else:
            for channel in channels:
                id, channel_id, name, is_active = channel
                status = "✅ Активен" if is_active else "❌ Неактивен"
                channels_text += f"ID: {id} | {name} | {status}\n"
                channels_text += f"Telegram ID: {channel_id}\n\n"
        
        channels_text += f"{hbold('Выберите действие:')}"
        
        await callback_query.message.edit_text(
            channels_text, 
            parse_mode="HTML",
            reply_markup=get_channels_keyboard()
        )
    except Exception as e:
        logger.error(f"[DEBUG] Error in process_admin_channels: {e}", exc_info=True)
        await callback_query.message.edit_text(
            "Произошла ошибка при получении списка каналов.",
            reply_markup=get_admin_keyboard()
        )

# Обработчик подписок для callback
async def process_admin_subs(callback_query: types.CallbackQuery, session):
    """Process admin_subs callback"""
    try:
        # Check if user is admin
        user_id = callback_query.from_user.id
        if not await is_admin(session, user_id):
            await callback_query.answer("У вас нет прав администратора.")
            return
            
        # Get recent active subscriptions (limit 10)
        query = text("""
            SELECT s.id, u.user_id, u.username, c.name, t.name, s.start_date, s.end_date
            FROM subscriptions s
            JOIN users u ON s.user_id = u.id
            JOIN channels c ON s.channel_id = c.id
            JOIN tariffs t ON s.tariff_id = t.id
            WHERE s.is_active = true
            ORDER BY s.start_date DESC
            LIMIT 10
        """)
        subscriptions = await session.execute(query)
        subscriptions = subscriptions.all()
        
        subs_text = f"{hbold('Последние активные подписки:')}\n\n"
        
        if not subscriptions:
            subs_text += "Нет активных подписок.\n\n"
        else:
            for sub in subscriptions:
                id, user_id, username, channel, tariff, start_date, end_date = sub
                subs_text += f"ID: {id} | Пользователь: @{username or 'без юзернейма'} ({user_id})\n"
                subs_text += f"Канал: {channel} | Тариф: {tariff}\n"
                subs_text += f"Начало: {start_date.strftime('%d.%m.%Y')} | Окончание: {end_date.strftime('%d.%m.%Y')}\n\n"
        
        subs_text += f"{hbold('Выберите действие:')}"
        
        await callback_query.message.edit_text(
            subs_text, 
            parse_mode="HTML",
            reply_markup=get_subscriptions_keyboard()
        )
    except Exception as e:
        logger.error(f"[DEBUG] Error in process_admin_subs: {e}", exc_info=True)
        await callback_query.message.edit_text(
            "Произошла ошибка при получении списка подписок.",
            reply_markup=get_admin_keyboard()
        )

# Admin stats command handler
async def cmd_admin_stats(message: types.Message):
    """Handle /admin_stats command - show bot statistics"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_admin_stats for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for admin_stats with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
                
            # Get statistics from database
            stats = {}
            
            # Users count
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            stats['users_total'] = result.scalar() or 0
            
            # Active users (with at least one active subscription)
            result = await session.execute(
                text("""
                SELECT COUNT(DISTINCT user_id) 
                FROM subscriptions 
                WHERE is_active = true
                """)
            )
            stats['users_active'] = result.scalar() or 0
            
            # Channels count
            result = await session.execute(text("SELECT COUNT(*) FROM channels"))
            stats['channels_total'] = result.scalar() or 0
            
            # Active channels
            result = await session.execute(
                text("SELECT COUNT(*) FROM channels WHERE is_active = true")
            )
            stats['channels_active'] = result.scalar() or 0
            
            # Subscriptions count
            result = await session.execute(text("SELECT COUNT(*) FROM subscriptions"))
            stats['subscriptions_total'] = result.scalar() or 0
            
            # Active subscriptions
            result = await session.execute(
                text("SELECT COUNT(*) FROM subscriptions WHERE is_active = true")
            )
            stats['subscriptions_active'] = result.scalar() or 0
            
            # Average subscriptions per user
            if stats['users_total'] > 0:
                stats['avg_subs_per_user'] = round(stats['subscriptions_total'] / stats['users_total'], 2)
            else:
                stats['avg_subs_per_user'] = 0
                
            # Average active subscriptions per active user
            if stats['users_active'] > 0:
                stats['avg_active_subs_per_user'] = round(stats['subscriptions_active'] / stats['users_active'], 2)
            else:
                stats['avg_active_subs_per_user'] = 0
                
            # Format message
            stats_text = f"{hbold('Статистика бота')}\n\n"
            
            stats_text += f"👤 {hbold('Пользователи:')}\n"
            stats_text += f"   • Всего: {stats['users_total']}\n"
            stats_text += f"   • Активных: {stats['users_active']} ({round(stats['users_active']/stats['users_total']*100, 1)}% от общего числа)\n\n"
            
            stats_text += f"📺 {hbold('Каналы:')}\n"
            stats_text += f"   • Всего: {stats['channels_total']}\n"
            stats_text += f"   • Активных: {stats['channels_active']} ({round(stats['channels_active']/stats['channels_total']*100, 1) if stats['channels_total'] > 0 else 0}% от общего числа)\n\n"
            
            stats_text += f"🔗 {hbold('Подписки:')}\n"
            stats_text += f"   • Всего: {stats['subscriptions_total']}\n"
            stats_text += f"   • Активных: {stats['subscriptions_active']} ({round(stats['subscriptions_active']/stats['subscriptions_total']*100, 1) if stats['subscriptions_total'] > 0 else 0}% от общего числа)\n\n"
            
            stats_text += f"📊 {hbold('В среднем:')}\n"
            stats_text += f"   • {stats['avg_subs_per_user']} подписок на пользователя\n"
            stats_text += f"   • {stats['avg_active_subs_per_user']} активных подписок на активного пользователя\n"
                
            # Show stats
            await message.answer(stats_text, parse_mode="HTML")
            await engine.dispose()
            
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_admin_stats: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении статистики.")

# Admin channels command handler
async def cmd_admin_channels(message: types.Message):
    """Command /admin_channels - показывает статистику по каналам."""
    try:
        user_id = message.from_user.id
        
        # Create a fresh database connection for this event loop
        import os
        from dotenv import load_dotenv
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Load environment variables if needed
        load_dotenv()
        
        # Get database URL
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
        logger.info(f"[DEBUG] Creating new DB engine for admin_channels with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Проверяем права администратора
            if not await is_admin(session, user_id):
                await message.answer("⛔️ У вас нет прав для выполнения этой команды.")
                await engine.dispose()
                return
            
            logger.debug(f"Admin {user_id} requested channels statistics")
            
            # Получаем статистику по каналам
            # Общее количество каналов
            total_channels = await session.scalar(
                text("SELECT COUNT(*) FROM channels")
            )
            
            # Активные каналы
            active_channels = await session.scalar(
                text("SELECT COUNT(*) FROM channels WHERE is_active = true")
            )
            
            # Каналы с наибольшим количеством подписчиков (подписок)
            top_channels = await session.execute(
                text("""
                SELECT 
                    c.id,
                    c.channel_id,
                    c.name,
                    c.is_active,
                    COUNT(s.id) as subscription_count
                FROM 
                    channels c
                LEFT JOIN 
                    subscriptions s ON c.id = s.channel_id AND s.is_active = true
                GROUP BY 
                    c.id, c.channel_id, c.name, c.is_active
                ORDER BY 
                    subscription_count DESC
                LIMIT 10
                """)
            )
            top_channels_list = top_channels.fetchall()
            
            # Формируем ответ
            response = [
                f"📺 <b>Статистика каналов:</b>\n",
                f"📢 Всего каналов: <b>{total_channels}</b>",
                f"✅ Активных каналов: <b>{active_channels}</b>\n",
                f"🏆 <b>Топ-10 каналов по количеству подписок:</b>"
            ]
            
            for channel in top_channels_list:
                status = "✅" if channel[3] else "❌"
                response.append(
                    f"• {status} {channel[2]} | ID: {channel[1]} | {channel[4]:,} подписчиков"
                )
            
            await message.answer("\n".join(response), parse_mode="HTML")
            await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error in cmd_admin_channels: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")

# Admin subscriptions command handler
async def cmd_admin_subscriptions(message: types.Message):
    """Handle /admin_subscriptions command - show subscription details"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_admin_subscriptions for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for admin_subscriptions with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Get statistics
            # Active subscriptions
            active_result = await session.execute(
                text("SELECT COUNT(*) FROM subscriptions WHERE is_active = true")
            )
            active_subs = active_result.scalar() or 0
            
            # Inactive subscriptions
            inactive_result = await session.execute(
                text("SELECT COUNT(*) FROM subscriptions WHERE is_active = false")
            )
            inactive_subs = inactive_result.scalar() or 0
            
            # Subscriptions by channel
            channels_result = await session.execute(
                text("""
                SELECT 
                    c.id,
                    c.channel_id,
                    c.name,
                    COUNT(s.id) as total_subs,
                    SUM(CASE WHEN s.is_active = true THEN 1 ELSE 0 END) as active_subs
                FROM 
                    channels c
                LEFT JOIN 
                    subscriptions s ON c.id = s.channel_id
                GROUP BY 
                    c.id, c.channel_id, c.name
                ORDER BY 
                    active_subs DESC
                LIMIT 15
                """)
            )
            
            channels_subs = channels_result.fetchall()
            
            # Format response
            response_text = f"{hbold('Статистика подписок')}\n\n"
            response_text += f"Активных подписок: {active_subs}\n"
            response_text += f"Неактивных подписок: {inactive_subs}\n"
            response_text += f"Всего подписок: {active_subs + inactive_subs}\n\n"
            
            response_text += f"{hbold('Топ-15 каналов по подпискам:')}\n\n"
            
            for idx, channel in enumerate(channels_subs, 1):
                channel_id = channel[1] or "Неизвестный ID"
                channel_title = channel[2] or "Неизвестный канал"
                total_subs = channel[3] or 0
                active_subs = channel[4] or 0
                
                response_text += f"{idx}. {hbold(channel_title)}\n"
                response_text += f"   • ID канала: {channel_id}\n"
                response_text += f"   • Всего подписок: {total_subs}\n"
                response_text += f"   • Активных подписок: {active_subs}\n\n"
            
            # Recent subscriptions
            recent_result = await session.execute(
                text("""
                SELECT 
                    s.id,
                    s.user_id,
                    u.username,
                    c.name as channel_title,
                    s.created_at,
                    s.is_active
                FROM 
                    subscriptions s
                LEFT JOIN 
                    users u ON s.user_id = u.id
                LEFT JOIN 
                    channels c ON s.channel_id = c.id
                ORDER BY 
                    s.created_at DESC
                LIMIT 10
                """)
            )
            
            recent_subs = recent_result.fetchall()
            
            response_text += f"{hbold('Последние 10 подписок:')}\n\n"
            
            for sub in recent_subs:
                sub_id = sub[0]
                user_id = sub[1]
                username = sub[2] or "Неизвестный пользователь"
                channel_title = sub[3] or "Неизвестный канал"
                created_at = sub[4].strftime('%d.%m.%Y %H:%M') if sub[4] else "Не указано"
                is_active = "Активна" if sub[5] else "Неактивна"
                
                response_text += f"{hbold(f'Подписка ID: {sub_id}')}\n"
                response_text += f"   • Пользователь: {username} (ID: {user_id})\n"
                response_text += f"   • Канал: {channel_title}\n"
                response_text += f"   • Дата создания: {created_at}\n"
                response_text += f"   • Статус: {is_active}\n\n"
            
            # Show statistics
            await message.answer(response_text, parse_mode="HTML")
            await engine.dispose()
            
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_admin_subscriptions: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении статистики подписок.")

# Add channel command handler
async def cmd_add_channel(message: types.Message):
    """Handle /add_channel command - add a new channel"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_add_channel for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for add_channel with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Parse command arguments
            try:
                _, channel_id, *name_parts = message.text.split()
                channel_id = int(channel_id)
                name = " ".join(name_parts)
                
                if not name:
                    raise ValueError("Name is required")
                    
            except ValueError as e:
                await message.answer(
                    f"❌ Ошибка в формате команды: {e}\n"
                    f"Формат: /add_channel CHANNEL_ID NAME"
                )
                await engine.dispose()
                return
            
            # Check if channel already exists
            existing_channel = await session.scalar(
                text("SELECT id FROM channels WHERE channel_id = :channel_id").bindparams(channel_id=channel_id)
            )
            
            if existing_channel:
                await message.answer(f"❌ Канал с ID {channel_id} уже существует.")
                await engine.dispose()
                return
            
            # Add channel to database
            try:
                # Create new channel
                await session.execute(
                    text("INSERT INTO channels (channel_id, name, is_active) VALUES (:channel_id, :name, true)"),
                    {"channel_id": channel_id, "name": name}
                )
                await session.commit()
                
                await message.answer(f"✅ Канал {name} успешно добавлен!")
            except Exception as e:
                logger.error(f"Failed to add channel: {e}")
                await message.answer(f"❌ Ошибка при добавлении канала: {e}")
            
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_add_channel: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Toggle channel command handler
async def cmd_toggle_channel(message: types.Message):
    """Handle /toggle_channel command - toggle channel active status"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_toggle_channel for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for toggle_channel with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Parse command arguments
            try:
                _, channel_id = message.text.split()
                channel_id = int(channel_id)
            except ValueError:
                await message.answer(
                    "❌ Ошибка в формате команды.\n"
                    "Формат: /toggle_channel CHANNEL_ID"
                )
                await engine.dispose()
                return
            
            # Check if channel exists
            channel = await session.scalar(
                text("SELECT is_active FROM channels WHERE id = :channel_id").bindparams(channel_id=channel_id)
            )
            
            if channel is None:
                await message.answer(f"❌ Канал с ID {channel_id} не найден.")
                await engine.dispose()
                return
            
            # Toggle channel status
            try:
                new_status = not channel
                await session.execute(
                    text("UPDATE channels SET is_active = :new_status WHERE id = :channel_id"),
                    {"new_status": new_status, "channel_id": channel_id}
                )
                await session.commit()
                
                status_text = "активирован" if new_status else "деактивирован"
                await message.answer(f"✅ Канал успешно {status_text}!")
            except Exception as e:
                logger.error(f"Failed to toggle channel: {e}")
                await message.answer(f"❌ Ошибка при изменении статуса канала: {e}")
            
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_toggle_channel: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Add tariff command handler
async def cmd_add_tariff(message: types.Message):
    """Handle /add_tariff command - add a new tariff"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_add_tariff for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for add_tariff with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Parse command arguments
            try:
                parts = message.text.split()
                if len(parts) < 5:
                    raise ValueError("Not enough arguments")
                    
                _, channel_id, name, days, price = parts[0], int(parts[1]), parts[2], int(parts[3]), int(parts[4])
                
                # Check if channel exists
                channel = await session.scalar(
                    text("SELECT id FROM channels WHERE channel_id = :channel_id").bindparams(channel_id=channel_id)
                )
                
                if channel is None:
                    await message.answer(f"❌ Канал с ID {channel_id} не найден.")
                    await engine.dispose()
                    return
                
            except ValueError as e:
                await message.answer(
                    f"❌ Ошибка в формате команды: {e}\n"
                    f"Формат: /add_tariff CHANNEL_ID NAME DAYS PRICE"
                )
                await engine.dispose()
                return
            
            # Add tariff to database
            try:
                # Create new tariff
                await session.execute(
                    text("""
                    INSERT INTO tariffs (channel_id, name, description, duration_days, price_stars, is_active) 
                    VALUES (:channel_id, :name, :description, :duration_days, :price_stars, 1)
                    """),
                    {
                        "channel_id": channel_id, 
                        "name": name, 
                        "description": f"Подписка на {days} дней",
                        "duration_days": days,
                        "price_stars": price
                    }
                )
                await session.commit()
                
                await message.answer(
                    f"✅ Тариф {name} успешно добавлен!\n"
                    f"Длительность: {days} дней\n"
                    f"Цена: {price} Stars"
                )
            except Exception as e:
                logger.error(f"Failed to add tariff: {e}")
                await message.answer(f"❌ Ошибка при добавлении тарифа: {e}")
            
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_add_tariff: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Add subscription command handler
async def cmd_add_sub(message: types.Message):
    """Handle /add_sub command - add a subscription manually"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_add_sub for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for add_sub with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Parse command arguments
            try:
                _, target_user_id, channel_id, tariff_id = message.text.split()
                target_user_id = int(target_user_id)
                channel_id = int(channel_id)
                tariff_id = int(tariff_id)
                
                # Check if user exists
                user = await session.scalar(
                    text("SELECT id FROM users WHERE user_id = :user_id").bindparams(user_id=target_user_id)
                )
                
                if user is None:
                    await message.answer(f"❌ Пользователь с ID {target_user_id} не найден.")
                    await engine.dispose()
                    return
                    
                # Check if channel exists
                channel = await session.scalar(
                    text("SELECT id FROM channels WHERE channel_id = :channel_id").bindparams(channel_id=channel_id)
                )
                
                if channel is None:
                    await message.answer(f"❌ Канал с ID {channel_id} не найден.")
                    await engine.dispose()
                    return
                    
                # Check if tariff exists
                tariff_query = await session.execute(
                    text("SELECT id, duration_days FROM tariffs WHERE id = :tariff_id").bindparams(tariff_id=tariff_id)
                )
                tariff = tariff_query.first()
                
                if tariff is None:
                    await message.answer(f"❌ Тариф с ID {tariff_id} не найден.")
                    await engine.dispose()
                    return
                    
                duration_days = tariff[1]
                
            except ValueError:
                await message.answer(
                    "❌ Ошибка в формате команды.\n"
                    "Формат: /add_sub USER_ID CHANNEL_ID TARIFF_ID"
                )
                await engine.dispose()
                return
            
            # Add subscription to database
            try:
                # Calculate end date
                start_date = datetime.utcnow()
                end_date = start_date.replace(
                    day=(start_date.day + duration_days) % 30 or 30,
                    month=start_date.month + (start_date.day + duration_days) // 30
                )
                
                # Create new subscription
                await session.execute(
                    text("""
                    INSERT INTO subscriptions 
                    (user_id, channel_id, tariff_id, start_date, end_date, is_active) 
                    VALUES (:user_id, :channel_id, :tariff_id, :start_date, :end_date, true)
                    """),
                    {
                        "user_id": user, 
                        "channel_id": channel, 
                        "tariff_id": tariff_id,
                        "start_date": start_date,
                        "end_date": end_date
                    }
                )
                await session.commit()
                
                # Generate invite link
                try:
                    channel_tg_id = await session.scalar(
                        text("SELECT channel_id FROM channels WHERE id = :channel_id").bindparams(channel_id=channel_id)
                    )
                    invite_link = await message.bot.create_chat_invite_link(
                        chat_id=channel_tg_id,
                        expire_date=datetime.now() + timedelta(hours=1),
                        member_limit=1
                    )
                    link_text = f"\n\nПригласительная ссылка: {invite_link.invite_link}"
                except Exception as e:
                    logger.error(f"Failed to generate invite link: {e}")
                    link_text = "\n\nНе удалось создать пригласительную ссылку."
                
                await message.answer(
                    f"✅ Подписка успешно добавлена!\n"
                    f"Пользователь: {target_user_id}\n"
                    f"Канал ID: {channel_id}\n"
                    f"Тариф ID: {tariff_id}\n"
                    f"Действует до: {end_date.strftime('%d.%m.%Y')}"
                    f"{link_text}"
                )
            except Exception as e:
                logger.error(f"Failed to add subscription: {e}")
                await message.answer(f"❌ Ошибка при добавлении подписки: {e}")
            
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_add_sub: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Delete subscription command handler
async def cmd_del_sub(message: types.Message):
    """Handle /del_sub command - delete a subscription"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_del_sub for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for del_sub with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Parse command arguments
            try:
                _, sub_id = message.text.split()
                sub_id = int(sub_id)
            except ValueError:
                await message.answer(
                    "❌ Ошибка в формате команды.\n"
                    "Формат: /del_sub SUBSCRIPTION_ID"
                )
                await engine.dispose()
                return
            
            # Check if subscription exists
            sub_query = await session.execute(
                text("""
                SELECT s.id, u.user_id, c.channel_id, c.name
                FROM subscriptions s
                JOIN users u ON s.user_id = u.id
                JOIN channels c ON s.channel_id = c.id
                WHERE s.id = :sub_id
                """).bindparams(sub_id=sub_id)
            )
            sub = sub_query.first()
            
            if sub is None:
                await message.answer(f"❌ Подписка с ID {sub_id} не найдена.")
                await engine.dispose()
                return
            
            # Delete subscription from database
            try:
                # Mark subscription as inactive
                await session.execute(
                    text("UPDATE subscriptions SET is_active = false WHERE id = :sub_id").bindparams(sub_id=sub_id)
                )
                await session.commit()
                
                # Try to kick user from channel
                try:
                    await message.bot.ban_chat_member(
                        chat_id=sub[2],  # channel_id
                        user_id=sub[1],  # user_id
                    )
                    
                    # Immediately unban so user can re-subscribe later
                    await message.bot.unban_chat_member(
                        chat_id=sub[2],  # channel_id
                        user_id=sub[1],  # user_id
                        only_if_banned=True
                    )
                    
                    kick_text = "\nПользователь удален из канала."
                except Exception as e:
                    logger.error(f"Failed to kick user from channel: {e}")
                    kick_text = "\nНе удалось удалить пользователя из канала."
                
                await message.answer(
                    f"✅ Подписка успешно деактивирована!\n"
                    f"ID: {sub_id}\n"
                    f"Пользователь: {sub[1]}\n"
                    f"Канал: {sub[3]}{kick_text}"
                )
            except Exception as e:
                logger.error(f"Failed to deactivate subscription: {e}")
                await message.answer(f"❌ Ошибка при деактивации подписки: {e}")
            
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_del_sub: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Admin users command handler
async def cmd_admin_users(message: types.Message):
    """Command /admin_users - показывает статистику по пользователям."""
    try:
        user_id = message.from_user.id
        
        # Create a fresh database connection for this event loop
        import os
        from dotenv import load_dotenv
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Load environment variables if needed
        load_dotenv()
        
        # Get database URL
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
        logger.info(f"[DEBUG] Creating new DB engine for admin_users with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Проверяем права администратора
            if not await is_admin(session, user_id):
                await message.answer("⛔️ У вас нет прав для выполнения этой команды.")
                await engine.dispose()
                return
            
            logger.debug(f"Admin {user_id} requested users statistics")
            
            # Получаем общее количество пользователей
            total_users = await session.scalar(
                text("SELECT COUNT(*) FROM users")
            )
            
            # Количество пользователей за последние 7 дней
            week_ago = datetime.now() - timedelta(days=7)
            new_users_week = await session.scalar(
                text("SELECT COUNT(*) FROM users WHERE created_at >= :week_ago").bindparams(week_ago=week_ago)
            )
            
            # Количество активных пользователей (отправивших сообщение за последние 30 дней)
            month_ago = datetime.now() - timedelta(days=30)
            active_users = await session.scalar(
                text("SELECT COUNT(*) FROM users WHERE last_active >= :month_ago").bindparams(month_ago=month_ago)
            )
            
            # Последние 10 зарегистрированных пользователей
            latest_users = await session.execute(
                text("SELECT user_id, username, created_at FROM users ORDER BY created_at DESC LIMIT 10")
            )
            latest_users_list = latest_users.fetchall()
            
            # Формируем ответ
            response = [
                f"📊 <b>Статистика пользователей:</b>\n",
                f"👥 Всего пользователей: <b>{total_users}</b>",
                f"🆕 Новых за неделю: <b>{new_users_week}</b>",
                f"🔄 Активных за месяц: <b>{active_users}</b>\n",
                f"🔍 <b>Последние 10 пользователей:</b>"
            ]
            
            for user in latest_users_list:
                user_id, username, created_at = user
                username_display = f"@{username}" if username else "Без username"
                created_date = created_at.strftime('%d.%m.%Y') if created_at else "Дата неизвестна"
                response.append(
                    f"• ID: {user_id} | {username_display} | {created_date}"
                )
            
            await message.answer("\n".join(response), parse_mode="HTML")
            await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error in cmd_admin_users: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")

# Admin posts command handler
async def cmd_admin_posts(message: types.Message):
    """Command /admin_posts - показывает статистику по постам."""
    try:
        user_id = message.from_user.id
        
        # Create a fresh database connection for this event loop
        import os
        from dotenv import load_dotenv
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Load environment variables if needed
        load_dotenv()
        
        # Get database URL
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_database.db")
        logger.info(f"[DEBUG] Creating new DB engine for admin_posts with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Проверяем права администратора
            if not await is_admin(session, user_id):
                await message.answer("⛔️ У вас нет прав для выполнения этой команды.")
                await engine.dispose()
                return
            
            logger.debug(f"Admin {user_id} requested posts statistics")
            
            # Получаем статистику по постам
            # Общее количество постов
            total_posts = await session.scalar(
                text("SELECT COUNT(*) FROM posts")
            )
            
            # Количество постов за последние 7 дней
            week_ago = datetime.now() - timedelta(days=7)
            new_posts_week = await session.scalar(
                text("SELECT COUNT(*) FROM posts WHERE created_at >= :week_ago").bindparams(week_ago=week_ago)
            )
            
            # Количество постов по каналам
            channel_stats = await session.execute(
                text("""
                SELECT 
                    c.name,
                    COUNT(p.id) as post_count
                FROM 
                    posts p
                JOIN 
                    channels c ON p.channel_id = c.id
                GROUP BY 
                    c.id, c.name
                ORDER BY 
                    post_count DESC
                LIMIT 10
                """)
            )
            channel_stats_list = channel_stats.fetchall()
            
            # Последние 5 постов
            latest_posts = await session.execute(
                text("""
                SELECT 
                    p.id,
                    p.created_at,
                    p.text,
                    c.name
                FROM 
                    posts p
                JOIN
                    channels c ON p.channel_id = c.id
                ORDER BY 
                    p.created_at DESC
                LIMIT 5
                """)
            )
            latest_posts_list = latest_posts.fetchall()
            
            # Формируем ответ
            response = [
                f"📝 <b>Статистика постов:</b>\n",
                f"📄 Всего постов: <b>{total_posts}</b>",
                f"🆕 Новых за неделю: <b>{new_posts_week}</b>\n",
                f"📊 <b>Топ-10 каналов по количеству постов:</b>"
            ]
            
            for channel_name, post_count in channel_stats_list:
                channel_name = channel_name or "Неизвестный канал"
                response.append(f"• {channel_name}: <b>{post_count}</b> постов")
            
            response.append("\n🔍 <b>Последние 5 постов:</b>")
            
            for post in latest_posts_list:
                post_id, created_at, text, channel_name = post
                created_date = created_at.strftime('%d.%m.%Y %H:%M') if created_at else "Дата неизвестна"
                channel_name = channel_name or "Неизвестный канал"
                truncated_text = text[:50] + "..." if text and len(text) > 50 else "Нет текста"
                response.append(
                    f"• {created_date} | {channel_name} | {truncated_text}"
                )
            
            await message.answer("\n".join(response), parse_mode="HTML")
            await engine.dispose()
        
    except Exception as e:
        logger.error(f"Error in cmd_admin_posts: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")

# Register admin handlers
def register_admin_handlers(dp: Dispatcher):
    """Register all admin handlers"""
    dp.register_message_handler(cmd_admin, Command("admin"))
    dp.register_message_handler(cmd_admin_stats, Command("admin_stats"))
    dp.register_message_handler(cmd_admin_channels, Command("admin_channels"))
    dp.register_message_handler(cmd_admin_subscriptions, Command("admin_subscriptions"))
    dp.register_message_handler(cmd_admin_users, Command("admin_users"))
    dp.register_message_handler(cmd_admin_posts, Command("admin_posts"))
    
    dp.register_message_handler(cmd_add_channel, Command("add_channel"))
    dp.register_message_handler(cmd_toggle_channel, Command("toggle_channel"))
    dp.register_message_handler(cmd_add_tariff, Command("add_tariff"))
    dp.register_message_handler(cmd_add_sub, Command("add_sub"))
    dp.register_message_handler(cmd_del_sub, Command("del_sub"))
    
    # Регистрируем обработчик callback-запросов
    dp.register_callback_query_handler(admin_callback_handler, lambda c: c.data in [
        "admin_stats", "admin_channels", "admin_subs", "back_to_admin", 
        "add_channel", "toggle_channel", "add_tariff", "add_sub", "del_sub"
    ]) 