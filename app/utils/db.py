from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from typing import TypeVar, Type, Optional, List, Callable, Any

from app.models.base import Base

T = TypeVar('T', bound=Base)

@asynccontextmanager
async def get_session(session_factory):
    """Context manager to handle database sessions"""
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

async def get_by_id(session: AsyncSession, model: Type[T], id: int) -> Optional[T]:
    """Get model instance by ID"""
    result = await session.execute(select(model).filter_by(id=id))
    return result.scalar_one_or_none()

async def get_by_filters(session: AsyncSession, model: Type[T], **filters) -> Optional[T]:
    """Get model instance by filters"""
    result = await session.execute(select(model).filter_by(**filters))
    return result.scalar_one_or_none()

async def get_all(session: AsyncSession, model: Type[T], **filters) -> List[T]:
    """Get all model instances by filters"""
    result = await session.execute(select(model).filter_by(**filters))
    return result.scalars().all()

async def create_object(session: AsyncSession, model: Type[T], **kwargs) -> T:
    """Create a new model instance"""
    obj = model(**kwargs)
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj

async def update_object(session: AsyncSession, obj: T, **kwargs) -> T:
    """Update model instance"""
    for key, value in kwargs.items():
        setattr(obj, key, value)
    await session.flush()
    await session.refresh(obj)
    return obj

async def delete_object(session: AsyncSession, obj: T) -> None:
    """Delete model instance"""
    await session.delete(obj)
    await session.flush() 