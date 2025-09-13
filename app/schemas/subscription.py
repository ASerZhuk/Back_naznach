from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from ..models.subscription import SubscriptionPlan, SubscriptionStatus


class SubscriptionPlanInfo(BaseModel):
    plan_type: SubscriptionPlan
    name: str
    price: int  # в копейках
    duration_days: int
    discount_percent: Optional[int] = None


class SubscriptionCreate(BaseModel):
    plan_type: SubscriptionPlan
    specialist_id: str


class SubscriptionResponse(BaseModel):
    id: int
    specialist_id: str
    plan_type: SubscriptionPlan
    status: SubscriptionStatus
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trial_start_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    payment_id: Optional[str] = None
    amount_paid: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True



class SubscriptionStatusCheck(BaseModel):
    has_active_subscription: bool
    is_trial_active: bool
    days_remaining: Optional[int] = None
    subscription: Optional[SubscriptionResponse] = None
    trial_end_date: Optional[datetime] = None


class PaymentCreateRequest(BaseModel):
    plan_type: SubscriptionPlan
    specialist_id: str

