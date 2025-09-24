import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from ..core.database import get_db
from ..services.subscription_service import SubscriptionService
from ..schemas.subscription import (
    SubscriptionResponse, SubscriptionStatusCheck,
)
from ..schemas.subscription_plan import SubscriptionPlanResponse
from .deps import require_auth
from ..services.telegram_bot import send_telegram_notification

logger = logging.getLogger(__name__)

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


@router.post("/payments/webhook")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Webhook от YooKassa для уведомлений о статусе платежей."""
    payload = await request.json()
    event = payload.get("event")

    if not event:
        raise HTTPException(status_code=400, detail="Отсутствует поле event")

    if event != "payment.succeeded":
        logger.info("Webhook %s проигнорирован", event)
        return {"status": "ignored"}

    payment_object = payload.get("object") or {}
    metadata = payment_object.get("metadata") or {}

    if metadata.get("type") != "subscription":
        logger.info("Webhook получен, но тип %s не поддерживается", metadata.get("type"))
        return {"status": "ignored"}

    specialist_id = metadata.get("specialistId")
    plan_type = metadata.get("planType")
    telegram_id = metadata.get("telegramId") or metadata.get("telegram_id")
    plan_name = metadata.get("planName")
    amount_info = payment_object.get("amount") or {}
    amount_value = amount_info.get("value")
    payment_id = payment_object.get("id")

    if not all([specialist_id, plan_type, amount_value, payment_id]):
        logger.error("Webhook: отсутствуют обязательные параметры %s", payload)
        raise HTTPException(status_code=400, detail="Отсутствуют обязательные параметры")

    try:
        amount_paid_kopecks = int(Decimal(str(amount_value)) * 100)
    except Exception as e:
        logger.error("Не удалось преобразовать сумму платежа: %s", e)
        raise HTTPException(status_code=400, detail="Неверный формат суммы")

    service = SubscriptionService(db)
    try:
        subscription = await service.activate_subscription(
            specialist_id,
            plan_type,
            payment_id,
            amount_paid_kopecks,
        )
    except ValueError as e:
        logger.warning("Ошибка при активации подписки: %s", e)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("Не удалось активировать подписку")
        raise HTTPException(status_code=500, detail="Не удалось активировать подписку")

    price_text = f"{Decimal(amount_paid_kopecks) / Decimal(100):.2f} ₽"
    plan_title = plan_name or plan_type

    if telegram_id:
        message = (
            "✅ <b>Подписка активирована</b>\n\n"
            f"Тариф: <b>{plan_title}</b>\n"
            f"Оплачено: <b>{price_text}</b>\n"
            "Спасибо за оплату!"
        )
        await send_telegram_notification(message=message, chat_id=telegram_id)

    logger.info(
        "Подписка активирована по платежу %s для специалиста %s", payment_id, specialist_id
    )
    return {"status": "processed"}
