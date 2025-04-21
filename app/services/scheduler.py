import logging
import os
import pytz
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from app.utils.db import get_session, get_all
from app.models import Subscription, User, Channel

logger = logging.getLogger(__name__)

async def check_expired_subscriptions(bot: Bot, session_factory):
    """Check for expired subscriptions and revoke access"""
    logger.info("Checking for expired subscriptions...")
    
    timezone = pytz.timezone(os.getenv("TIMEZONE", "UTC"))
    current_time = datetime.now(timezone).replace(tzinfo=None)
    
    async with get_session(session_factory) as session:
        # Get all active subscriptions that have expired
        expired_subscriptions = await get_all(
            session, 
            Subscription, 
            is_active=True
        )
        
        expired_subscriptions = [s for s in expired_subscriptions if s.end_date < current_time]
        
        if not expired_subscriptions:
            logger.info("No expired subscriptions found")
            return
        
        logger.info(f"Found {len(expired_subscriptions)} expired subscriptions")
        
        for subscription in expired_subscriptions:
            # Load related objects
            user = subscription.user
            channel = subscription.channel
            
            # Only process if we have the necessary data
            if not user or not channel:
                logger.warning(f"Missing user or channel data for subscription {subscription.id}")
                continue
            
            # Try to kick user from channel
            try:
                # Use ban method to ensure they can't rejoin with old invite links
                await bot.ban_chat_member(
                    chat_id=channel.channel_id,
                    user_id=user.user_id
                )
                
                # Immediately unban so user can re-subscribe later
                await bot.unban_chat_member(
                    chat_id=channel.channel_id,
                    user_id=user.user_id,
                    only_if_banned=True
                )
                
                # Mark subscription as inactive
                subscription.is_active = False
                await session.commit()
                
                # Notify user about subscription expiration
                try:
                    await bot.send_message(
                        chat_id=user.user_id,
                        text=f"Your subscription to {channel.name} has expired. "
                             f"You can renew your subscription using the /start command."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user.user_id} about subscription expiration: {e}")
                
                logger.info(f"Successfully revoked access for user {user.user_id} to channel {channel.name}")
                
            except Exception as e:
                logger.error(f"Failed to revoke access for user {user.user_id} to channel {channel.channel_id}: {e}")

def setup_scheduler(bot: Bot, session_factory):
    """Set up scheduler for periodic tasks"""
    scheduler = AsyncIOScheduler()
    
    # Convert interval from env to seconds
    interval_seconds = int(os.getenv("CHECK_SUBSCRIPTION_INTERVAL", 3600))
    
    # Schedule subscription checker job
    scheduler.add_job(
        check_expired_subscriptions,
        'interval',
        seconds=interval_seconds,
        kwargs={
            'bot': bot,
            'session_factory': session_factory
        }
    )
    
    # Start scheduler
    scheduler.start()
    
    logger.info(f"Scheduler started, checking subscriptions every {interval_seconds} seconds") 