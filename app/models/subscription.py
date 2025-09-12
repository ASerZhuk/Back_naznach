from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
import enum


class SubscriptionPlan(str, enum.Enum):
    MONTH = "month"
    SIX_MONTHS = "6months"
    YEAR = "year"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Subscription(Base):
    __tablename__ = "subscription"
    
    id = Column(Integer, primary_key=True, index=True)
    specialist_id = Column(String, ForeignKey("specialist.user_id"), nullable=False, index=True)
    plan_type = Column(Enum(SubscriptionPlan), nullable=False)
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.TRIAL)
    
    # Даты
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Платеж
    payment_id = Column(String, nullable=True)  # ID платежа в ЮKassa
    amount_paid = Column(Integer, nullable=True)  # Сумма в копейках
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    specialist = relationship("Specialist", back_populates="subscription")

