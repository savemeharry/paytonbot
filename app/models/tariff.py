from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import Base

class Tariff(Base):
    __tablename__ = "tariffs"
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    duration_days = Column(Integer, nullable=False)
    price_stars = Column(Integer, nullable=False)
    is_active = Column(Integer, default=True)
    
    # Relationship
    channel = relationship("Channel", backref="tariffs")
    
    def __repr__(self):
        return f"<Tariff(id={self.id}, name={self.name}, price={self.price_stars} stars, duration={self.duration_days} days)>" 