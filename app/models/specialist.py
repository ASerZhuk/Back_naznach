from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Specialist(Base):
    __tablename__ = "specialist"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    chat_id = Column(String, nullable=True)
    user_id = Column(String, ForeignKey("user.telegram_id"), unique=True, index=True)
    username = Column(String, nullable=True)
    image = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    category = Column(String, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String, nullable=True)
    address = Column(String, nullable=True)
    telegram_link = Column(String, nullable=True)
    
    # Поля подписки
    is_trial_used = Column(Boolean, default=False)
    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="specialist")
    grafiks = relationship("Grafik", back_populates="specialist")
    services = relationship("Service", back_populates="specialist")
    appointments = relationship("Appointments", back_populates="specialist")
    subscription = relationship("Subscription", back_populates="specialist", uselist=False)
