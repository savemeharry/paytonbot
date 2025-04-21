from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Boolean, String
from sqlalchemy.orm import relationship

from app.models.base import Base

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=False)
    telegram_payment_id = Column(String, nullable=True)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", backref="subscriptions")
    channel = relationship("Channel")
    tariff = relationship("Tariff")
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, channel_id={self.channel_id}, active until={self.end_date})>" 