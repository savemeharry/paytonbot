import logging
import os
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Tuple

from app.models import Channel, Tariff
from app.utils.db import get_by_filters, get_all, create_object

logger = logging.getLogger(__name__)

async def get_active_channels(session: AsyncSession) -> List[Channel]:
    """Get all active channels"""
    return await get_all(session, Channel, is_active=True)

async def get_channel_by_id(session: AsyncSession, channel_id: int) -> Optional[Channel]:
    """Get channel by ID"""
    return await get_by_filters(session, Channel, channel_id=channel_id)

async def get_channel_tariffs(session: AsyncSession, channel_id: int) -> List[Tariff]:
    """Get all tariffs for a channel"""
    channel = await get_by_filters(session, Channel, id=channel_id)
    if not channel:
        return []
    
    return await get_all(session, Tariff, channel_id=channel.id, is_active=True)

async def generate_invite_link(bot, chat_id: int) -> str:
    """Generate a temporary invite link for a channel/group"""
    expire_time = int(os.getenv("INVITE_LINK_EXPIRE_TIME", 3600))  # Default: 1 hour
    
    try:
        # Create an invite link that expires after specified time
        invite_link = await bot.create_chat_invite_link(
            chat_id=chat_id,
            expire_date=datetime.now() + timedelta(seconds=expire_time),
            member_limit=1  # One-time use link
        )
        
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"Failed to generate invite link for chat {chat_id}: {e}")
        raise 