import logging
import os
from decimal import Decimal
import aiohttp

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
    """Webhook от YooKassa: payment.succeeded / payment.canceled.
    Валидация через GET /v3/payments/{id}, идемпотентная активация, уведомления в Telegram."""
    payload = await request.json()
    event = payload.get("event")

    if not event:
        raise HTTPException(status_code=400, detail="Отсутствует поле event")

    if event not in ("payment.succeeded", "payment.canceled"):
        logger.info("Webhook %s проигнорирован", event)
        return {"status": "ignored"}

    payment_object = payload.get("object") or {}
    payment_id = payment_object.get("id")
    metadata = payment_object.get("metadata") or {}

    if metadata.get("type") != "subscription":
        logger.info("Webhook получен, но тип %s не поддерживается", metadata.get("type"))
        return {"status": "ignored"}

    # Попытка подтвердить данные напрямую у YooKassa
    shop_id = os.getenv("YKS_SHOP_ID")
    secret_key = os.getenv("YKS_SECRET_KEY")
    yk_data = None
    if shop_id and secret_key and payment_id:
        try:
            auth = f"{shop_id}:{secret_key}"
            headers = {"Authorization": "Basic " + (
                __import__('base64').b64encode(auth.encode()).decode()
            )}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.yookassa.ru/v3/payments/{payment_id}",
                    headers=headers,
                ) as resp:
                    if resp.status < 400:
                        yk_data = await resp.json()
                    else:
                        logger.warning("GET payments/%s вернул %s", payment_id, resp.status)
        except Exception:
            logger.exception("Не удалось подтвердить платеж в YooKassa")

    # Используем подтвержденные данные, если доступны
    if yk_data:
        payment_object = yk_data
        metadata = payment_object.get("metadata") or metadata or {}
        event_status = payment_object.get("status")
        # Приводим event к реальному статусу, если отличается
        if event_status == "succeeded":
            event = "payment.succeeded"
        elif event_status == "canceled":
            event = "payment.canceled"

    specialist_id = metadata.get("specialistId")
    plan_type = metadata.get("planType")
    telegram_id = metadata.get("telegramId") or metadata.get("telegram_id")
    plan_name = metadata.get("planName")

    amount_info = payment_object.get("amount") or {}
    amount_value = amount_info.get("value")  # string like '100.00'

    service = SubscriptionService(db)

    # Сценарий отмены/ошибки оплаты
    if event == "payment.canceled":
        if telegram_id:
            reason = (payment_object.get("cancellation_details") or {}).get("reason", "")
            message = (
                "❌ <b>Оплата не завершена</b>\n\n"
                f"Причина: <i>{reason or 'не указана'}</i>\n"
                "Вы можете попробовать оплатить снова из мини‑приложения."
            )
            await send_telegram_notification(message=message, chat_id=telegram_id)
        logger.info("Отмена/ошибка платежа %s", payment_id)
        return {"status": "canceled"}

    # Должны быть выполнены поля
    if not all([specialist_id, plan_type, payment_id, amount_value]):
        logger.error("Webhook: отсутствуют обязательные параметры %s", payload)
        raise HTTPException(status_code=400, detail="Отсутствуют обязательные параметры")

    try:
        amount_paid_kopecks = int(Decimal(str(amount_value)) * 100)
    except Exception as e:
        logger.error("Не удалось преобразовать сумму платежа: %s", e)
        raise HTTPException(status_code=400, detail="Неверный формат суммы")

    # Идемпотентность: если уже активировано этим платежом — выходим
    try:
        current = await service.get_current_subscription(specialist_id)
        if current and getattr(current, 'payment_id', None) == payment_id:
            logger.info("Платеж %s уже обработан", payment_id)
            return {"status": "ok"}
    except Exception:
        # Не мешаем основному потоку
        logger.debug("Не удалось проверить текущую подписку", exc_info=True)

    # Активируем подписку
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

    # Уведомление в Telegram
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
