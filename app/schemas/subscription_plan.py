from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SubscriptionPlanResponse(BaseModel):
    id: int
    plan_type: str
    name: str
    price: int  # в копейках
    duration_days: int
    discount_percent: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionPlanCreate(BaseModel):
    plan_type: str
    name: str
    price: int
    duration_days: int
    discount_percent: int = 0
    is_active: bool = True


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    duration_days: Optional[int] = None
    discount_percent: Optional[int] = None
    is_active: Optional[bool] = None
