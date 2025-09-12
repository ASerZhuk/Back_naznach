from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from ..core.database import Base


class SubscriptionPlanModel(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_type = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    price = Column(Integer, nullable=False)  # в копейках
    duration_days = Column(Integer, nullable=False)
    discount_percent = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<SubscriptionPlanModel(plan_type='{self.plan_type}', name='{self.name}', price={self.price})>"
