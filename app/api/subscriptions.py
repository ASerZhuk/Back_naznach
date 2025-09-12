from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services.subscription_service import SubscriptionService
from ..schemas.subscription import (
    SubscriptionResponse, SubscriptionStatusCheck, 
    PaymentCreateRequest, SubscriptionCreate
)
from ..schemas.subscription_plan import SubscriptionPlanResponse
from .deps import require_auth

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(db: AsyncSession = Depends(get_db)):
    """Получить доступные планы подписки"""
    service = SubscriptionService(db)
    return await service.get_available_plans()


@router.get("/current", response_model=SubscriptionStatusCheck, dependencies=[Depends(require_auth)])
async def get_current_subscription(
    specialist_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Получить текущую подписку специалиста"""
    try:
        service = SubscriptionService(db)
        return await service.check_subscription_status(specialist_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении подписки: {str(e)}")


@router.post("/create-trial", response_model=SubscriptionResponse, dependencies=[Depends(require_auth)])
async def create_trial_subscription(
    specialist_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Создать пробную подписку для специалиста"""
    try:
        service = SubscriptionService(db)
        return await service.create_trial_subscription(specialist_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании пробной подписки: {str(e)}")


@router.post("/activate", response_model=SubscriptionResponse, dependencies=[Depends(require_auth)])
async def activate_subscription(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """Активировать подписку после успешной оплаты"""
    try:
        specialist_id = request.get("specialist_id")
        plan_type = request.get("plan_type")
        payment_id = request.get("payment_id")
        amount_paid = request.get("amount_paid")
        
        if not all([specialist_id, plan_type, payment_id, amount_paid is not None]):
            raise ValueError("Отсутствуют обязательные параметры")
        
        service = SubscriptionService(db)
        return await service.activate_subscription(
            specialist_id, 
            plan_type, 
            payment_id, 
            amount_paid
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при активации подписки: {str(e)}")


@router.get("/check-access", dependencies=[Depends(require_auth)])
async def check_access(
    specialist_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Проверить доступ специалиста к функциям"""
    try:
        service = SubscriptionService(db)
        has_access = await service.has_access(specialist_id)
        return {"has_access": has_access}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при проверке доступа: {str(e)}")

