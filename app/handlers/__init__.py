from app.handlers.base import register_base_handlers
from app.handlers.subscription import register_subscription_handlers
from app.handlers.admin import register_admin_handlers

def register_all_handlers(dp):
    """Register all handlers"""
    # Register base handlers first
    register_base_handlers(dp)
    
    # Register subscription handlers
    register_subscription_handlers(dp)
    
    # Register admin handlers last
    register_admin_handlers(dp) 