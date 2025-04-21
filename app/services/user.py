import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.models import User
from app.utils.db import get_by_filters, create_object, update_object

logger = logging.getLogger(__name__)

async def get_or_create_user(
    session: AsyncSession, 
    user_id: int, 
    username: str = None,
    first_name: str = None,
    last_name: str = None
) -> User:
    """Get existing user or create a new one"""
    user = await get_by_filters(session, User, user_id=user_id)
    
    if user:
        # Update user info if it has changed
        updated = False
        update_data = {}
        
        if username is not None and user.username != username:
            update_data["username"] = username
            updated = True
            
        if first_name is not None and user.first_name != first_name:
            update_data["first_name"] = first_name
            updated = True
            
        if last_name is not None and user.last_name != last_name:
            update_data["last_name"] = last_name
            updated = True
            
        if updated:
            user = await update_object(session, user, **update_data)
            
        return user
    
    # Create new user
    # Check if user is an admin
    admin_ids = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
    is_admin = user_id in admin_ids
    
    user = await create_object(
        session,
        User,
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        is_admin=is_admin
    )
    
    logger.info(f"Created new user: {user}")
    return user

async def is_admin(session: AsyncSession, user_id: int) -> bool:
    """Check if user is an admin"""
    user = await get_by_filters(session, User, user_id=user_id)
    
    if not user:
        return False
        
    return user.is_admin 