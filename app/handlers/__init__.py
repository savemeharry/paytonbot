from app.handlers.base import register_base_handlers
from app.handlers.subscription import register_subscription_handlers
from app.handlers.admin import register_admin_handlers
import logging

logger = logging.getLogger(__name__)

def register_all_handlers(dp):
    """Register all handlers"""
    logger.info("Начинаем регистрацию обработчиков")
    
    # Register base handlers first
    logger.info("Регистрируем базовые обработчики")
    register_base_handlers(dp)
    
    # Register subscription handlers
    logger.info("Регистрируем обработчики подписок")
    register_subscription_handlers(dp)
    
    # Register admin handlers last
    logger.info("Регистрируем обработчики админа")
    register_admin_handlers(dp)
    
    logger.info("Регистрация обработчиков завершена") 