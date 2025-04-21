import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any, Tuple

from app.models import User, Channel, Tariff, Subscription
from app.utils.db import get_by_filters, get_all, create_object, update_object
from app.services.channel import generate_invite_link

logger = logging.getLogger(__name__)

async def get_user_subscriptions(session: AsyncSession, user_id: int) -> List[Subscription]:
    """Get all active subscriptions for a user"""
    user = await get_by_filters(session, User, user_id=user_id)
    if not user:
        return []
    
    return await get_all(session, Subscription, user_id=user.id, is_active=True)

async def is_subscribed(session: AsyncSession, user_id: int, channel_id: int) -> bool:
    """Check if user is subscribed to a channel"""
    user = await get_by_filters(session, User, user_id=user_id)
    channel = await get_by_filters(session, Channel, id=channel_id)
    
    if not user or not channel:
        return False
    
    subscription = await get_by_filters(
        session, 
        Subscription, 
        user_id=user.id, 
        channel_id=channel.id,
        is_active=True
    )
    
    return subscription is not None

async def create_subscription(
    session: AsyncSession, 
    user_id: int, 
    channel_id: int, 
    tariff_id: int,
    telegram_payment_id: str = None
) -> Tuple[Subscription, datetime]:
    """Create a new subscription"""
    user = await get_by_filters(session, User, user_id=user_id)
    tariff = await get_by_filters(session, Tariff, id=tariff_id)
    
    if not user or not tariff:
        logger.error(f"Failed to create subscription: User {user_id} or Tariff {tariff_id} not found")
        raise ValueError("User or Tariff not found")
    
    # Calculate end date based on tariff duration
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=tariff.duration_days)
    
    # Check if user already has an active subscription for this channel
    existing_sub = await get_by_filters(
        session, 
        Subscription, 
        user_id=user.id, 
        channel_id=tariff.channel_id,
        is_active=True
    )
    
    if existing_sub:
        # Extend existing subscription
        new_end_date = max(existing_sub.end_date, datetime.utcnow()) + timedelta(days=tariff.duration_days)
        subscription = await update_object(
            session,
            existing_sub,
            end_date=new_end_date,
            tariff_id=tariff.id,
            telegram_payment_id=telegram_payment_id
        )
    else:
        # Create new subscription
        subscription = await create_object(
            session,
            Subscription,
            user_id=user.id,
            channel_id=tariff.channel_id,
            tariff_id=tariff.id,
            start_date=start_date,
            end_date=end_date,
            telegram_payment_id=telegram_payment_id,
            is_active=True
        )
    
    return subscription, end_date

async def process_successful_payment(
    bot,
    session: AsyncSession,
    user_id: int,
    payment_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a successful payment and create subscription"""
    # Extract channel and tariff IDs from payment payload
    payload = payment_data.get("invoice_payload", "")
    parts = payload.split(":")
    
    if len(parts) != 3:
        logger.error(f"Invalid payment payload format: {payload}")
        raise ValueError("Invalid payment payload")
    
    user_id_from_payload, channel_id, tariff_id = int(parts[0]), int(parts[1]), int(parts[2])
    
    # Verify user ID matches
    if user_id != user_id_from_payload:
        logger.error(f"User ID mismatch: {user_id} != {user_id_from_payload}")
        raise ValueError("User ID mismatch")
    
    # Get channel info
    channel = await get_by_filters(session, Channel, id=channel_id)
    if not channel:
        logger.error(f"Channel not found: {channel_id}")
        raise ValueError("Channel not found")
    
    # Create or extend subscription
    subscription, end_date = await create_subscription(
        session,
        user_id,
        channel_id,
        tariff_id,
        payment_data.get("telegram_payment_charge_id")
    )
    
    # Generate invite link
    invite_link = await generate_invite_link(bot, channel.channel_id)
    
    return {
        "subscription": subscription,
        "channel": channel,
        "invite_link": invite_link,
        "end_date": end_date
    } 