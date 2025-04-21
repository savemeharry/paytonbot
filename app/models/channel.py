from sqlalchemy import Column, Integer, String, Boolean, Text

from app.models.base import Base

class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Channel(id={self.id}, channel_id={self.channel_id}, name={self.name})>" 