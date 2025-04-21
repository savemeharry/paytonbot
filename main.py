import logging
import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.handlers import register_all_handlers
from app.services.scheduler import setup_scheduler
from app.utils.logging import setup_logging

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=os.getenv("BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Database setup
async def init_db():
    engine = create_async_engine(
        os.getenv("DATABASE_URL").replace("sqlite:///", "sqlite+aiosqlite:///"), 
        echo=False
    )
    
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    return async_session

async def on_startup(dispatcher):
    # Create DB session factory
    session_factory = await init_db()
    
    # Set session factory for handlers
    dispatcher["session_factory"] = session_factory
    
    # Set payment provider token
    dispatcher["payment_provider_token"] = os.getenv("PAYMENT_PROVIDER_TOKEN")
    
    # Register all handlers
    register_all_handlers(dispatcher)
    
    # Set up scheduler for checking expired subscriptions
    setup_scheduler(bot, session_factory)
    
    # Notify admins about bot startup
    admin_ids = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, "Bot started successfully!")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    logger.info("Bot started!")

async def on_shutdown(dispatcher):
    logger.info("Shutting down...")
    # Close storage
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    logger.info("Bot stopped!")

if __name__ == "__main__":
    try:
        # Start the bot
        executor.start_polling(
            dp, 
            on_startup=on_startup, 
            on_shutdown=on_shutdown, 
            skip_updates=True
        )
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True) 