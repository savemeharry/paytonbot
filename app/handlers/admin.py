import logging
import re
from datetime import datetime, timedelta
from aiogram import Dispatcher, types
from aiogram.dispatcher.filters import Command
from aiogram.utils.markdown import hbold, hcode
from sqlalchemy import text

from app.utils.db import get_session
from app.services.user import is_admin
from app.models import User, Channel, Tariff, Subscription

logger = logging.getLogger(__name__)

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
            admin_text = (
                f"{hbold('Панель администратора:')}\n\n"
                f"/admin_stats - Статистика бота\n"
                f"/admin_channels - Управление каналами\n"
                f"/admin_subs - Управление подписками\n"
            )
            
            await message.answer(admin_text, parse_mode="HTML")
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_admin: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

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
            
            # Count statistics
            user_count = await session.scalar(
                text("SELECT COUNT(*) FROM users")
            )
            active_subs_count = await session.scalar(
                text("SELECT COUNT(*) FROM subscriptions WHERE is_active = 1")
            )
            channels_count = await session.scalar(
                text("SELECT COUNT(*) FROM channels")
            )
            
            # Show statistics
            stats_text = (
                f"{hbold('Статистика бота:')}\n\n"
                f"👤 Всего пользователей: {user_count}\n"
                f"📊 Активных подписок: {active_subs_count}\n"
                f"📺 Всего каналов: {channels_count}\n"
            )
            
            await message.answer(stats_text, parse_mode="HTML")
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_admin_stats: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Admin channels command handler
async def cmd_admin_channels(message: types.Message):
    """Handle /admin_channels command - show channels list"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_admin_channels for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for admin_channels with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Get all channels
            channels = await session.execute(
                text("SELECT id, channel_id, name, is_active FROM channels")
            )
            channels = channels.all()
            
            if not channels:
                await message.answer("Нет настроенных каналов.")
                await engine.dispose()
                return
            
            # Show channels list
            channels_text = f"{hbold('Список каналов:')}\n\n"
            
            for channel in channels:
                id, channel_id, name, is_active = channel
                status = "✅ Активен" if is_active else "❌ Неактивен"
                channels_text += f"ID: {id} | {name} | {status}\n"
                channels_text += f"Telegram ID: {channel_id}\n\n"
            
            channels_text += (
                f"\n{hbold('Команды управления:')}\n"
                f"/add_channel ID NAME - Добавить канал\n"
                f"/toggle_channel ID - Вкл/выкл канал\n"
                f"/add_tariff CHANNEL_ID NAME DAYS PRICE - Добавить тариф\n"
            )
            
            await message.answer(channels_text, parse_mode="HTML")
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_admin_channels: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Admin subscriptions command handler
async def cmd_admin_subs(message: types.Message):
    """Handle /admin_subs command - show recent subscriptions"""
    user_id = message.from_user.id
    logger.info(f"[DEBUG] cmd_admin_subs for user {user_id}")
    
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
        logger.info(f"[DEBUG] Creating new DB engine for admin_subs with URL: {db_url[:db_url.find(':')]}://...elided...")
        
        # Create new engine and session factory for this event loop
        engine = create_async_engine(db_url, echo=False, pool_timeout=30)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with get_session(session_factory) as session:
            # Check if user is admin
            if not await is_admin(session, user_id):
                await message.answer("У вас нет прав администратора.")
                await engine.dispose()
                return
            
            # Get recent active subscriptions (limit 10)
            query = text("""
                SELECT s.id, u.user_id, u.username, c.name, t.name, s.start_date, s.end_date
                FROM subscriptions s
                JOIN users u ON s.user_id = u.id
                JOIN channels c ON s.channel_id = c.id
                JOIN tariffs t ON s.tariff_id = t.id
                WHERE s.is_active = 1
                ORDER BY s.start_date DESC
                LIMIT 10
            """)
            subscriptions = await session.execute(query)
            subscriptions = subscriptions.all()
            
            if not subscriptions:
                await message.answer("Нет активных подписок.")
                await engine.dispose()
                return
            
            # Show subscriptions list
            subs_text = f"{hbold('Последние активные подписки:')}\n\n"
            
            for sub in subscriptions:
                id, user_id, username, channel, tariff, start_date, end_date = sub
                subs_text += f"ID: {id} | Пользователь: @{username or 'без юзернейма'} ({user_id})\n"
                subs_text += f"Канал: {channel} | Тариф: {tariff}\n"
                subs_text += f"Начало: {start_date.strftime('%d.%m.%Y')} | Окончание: {end_date.strftime('%d.%m.%Y')}\n\n"
            
            subs_text += (
                f"\n{hbold('Команды управления:')}\n"
                f"/add_sub USER_ID CHANNEL_ID TARIFF_ID - Добавить подписку\n"
                f"/del_sub SUB_ID - Удалить подписку\n"
            )
            
            await message.answer(subs_text, parse_mode="HTML")
            await engine.dispose()
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in cmd_admin_subs: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

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
                    text("INSERT INTO channels (channel_id, name, is_active) VALUES (:channel_id, :name, 1)"),
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
                new_status = 0 if channel else 1
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
                    text("SELECT id FROM channels WHERE id = :channel_id").bindparams(channel_id=channel_id)
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
                    text("SELECT id FROM channels WHERE id = :channel_id").bindparams(channel_id=channel_id)
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
                    VALUES (:user_id, :channel_id, :tariff_id, :start_date, :end_date, 1)
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
                    text("UPDATE subscriptions SET is_active = 0 WHERE id = :sub_id").bindparams(sub_id=sub_id)
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

# Register admin handlers
def register_admin_handlers(dp: Dispatcher):
    """Register all admin handlers"""
    dp.register_message_handler(cmd_admin, Command("admin"))
    dp.register_message_handler(cmd_admin_stats, Command("admin_stats"))
    dp.register_message_handler(cmd_admin_channels, Command("admin_channels"))
    dp.register_message_handler(cmd_admin_subs, Command("admin_subs"))
    
    dp.register_message_handler(cmd_add_channel, Command("add_channel"))
    dp.register_message_handler(cmd_toggle_channel, Command("toggle_channel"))
    dp.register_message_handler(cmd_add_tariff, Command("add_tariff"))
    dp.register_message_handler(cmd_add_sub, Command("add_sub"))
    dp.register_message_handler(cmd_del_sub, Command("del_sub")) 