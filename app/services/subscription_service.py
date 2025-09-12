from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from ..models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from ..models.subscription_plan import SubscriptionPlanModel
from ..models.specialist import Specialist
from ..schemas.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionStatusCheck
from ..schemas.subscription_plan import SubscriptionPlanResponse


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_available_plans(self) -> List[SubscriptionPlanResponse]:
        """Получить доступные планы подписки"""
        result = await self.db.execute(
            select(SubscriptionPlanModel).where(SubscriptionPlanModel.is_active == True)
        )
        plans = result.scalars().all()
        return [SubscriptionPlanResponse.model_validate(plan) for plan in plans]

    async def get_plan_info(self, plan_type: str) -> Optional[SubscriptionPlanResponse]:
        """Получить информацию о конкретном плане"""
        result = await self.db.execute(
            select(SubscriptionPlanModel).where(
                and_(
                    SubscriptionPlanModel.plan_type == plan_type,
                    SubscriptionPlanModel.is_active == True
                )
            )
        )
        plan = result.scalar_one_or_none()
        if plan:
            return SubscriptionPlanResponse.model_validate(plan)
        return None

    async def get_plan_duration_days(self, plan_type: str) -> int:
        """Получить количество дней для плана"""
        plan = await self.get_plan_info(plan_type)
        if plan:
            return plan.duration_days
        # Fallback для совместимости
        fallback_durations = {
            "month": 30,
            "six_months": 180,
            "year": 365
        }
        return fallback_durations.get(plan_type, 30)

    async def create_trial_subscription(self, specialist_id: str) -> SubscriptionResponse:
        """Создать пробную подписку на 14 дней для нового специалиста"""
        # Проверяем, есть ли уже подписка
        existing = await self.get_current_subscription(specialist_id)
        if existing:
            raise ValueError("У специалиста уже есть подписка")

        # Создаем пробную подписку
        trial_start = datetime.now(timezone.utc)
        trial_end = trial_start + timedelta(days=14)

        subscription = Subscription(
            specialist_id=specialist_id,
            plan_type=SubscriptionPlan.MONTH,  # По умолчанию месяц
            status=SubscriptionStatus.TRIAL,
            trial_start_date=trial_start,
            trial_end_date=trial_end
        )

        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        # Обновляем специалиста
        specialist = await self.db.get(Specialist, specialist_id)
        if specialist:
            specialist.is_trial_used = True
            specialist.trial_start_date = trial_start
            await self.db.commit()

        return SubscriptionResponse.model_validate(subscription)

    async def get_current_subscription(self, specialist_id: str) -> Optional[SubscriptionResponse]:
        """Получить текущую подписку специалиста"""
        result = await self.db.execute(
            select(Subscription).where(Subscription.specialist_id == specialist_id)
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            return None

        return SubscriptionResponse.model_validate(subscription)

    async def check_subscription_status(self, specialist_id: str) -> SubscriptionStatusCheck:
        """Проверить статус подписки специалиста"""
        subscription = await self.get_current_subscription(specialist_id)
        
        if not subscription:
            # Если нет подписки, создаем пробную
            subscription = await self.create_trial_subscription(specialist_id)

        now = datetime.now(timezone.utc)
        has_active_subscription = False
        is_trial_active = False
        days_remaining = None
        trial_end_date = None

        if subscription.status == SubscriptionStatus.TRIAL:
            if subscription.trial_end_date and subscription.trial_end_date > now:
                is_trial_active = True
                days_remaining = (subscription.trial_end_date - now).days
                trial_end_date = subscription.trial_end_date
            else:
                # Пробный период истек
                subscription.status = SubscriptionStatus.EXPIRED
                await self.db.commit()
        elif subscription.status == SubscriptionStatus.ACTIVE:
            if subscription.end_date and subscription.end_date > now:
                has_active_subscription = True
                days_remaining = (subscription.end_date - now).days
            else:
                # Подписка истекла
                subscription.status = SubscriptionStatus.EXPIRED
                await self.db.commit()

        return SubscriptionStatusCheck(
            has_active_subscription=has_active_subscription,
            is_trial_active=is_trial_active,
            days_remaining=days_remaining,
            subscription=subscription,
            trial_end_date=trial_end_date
        )

    async def activate_subscription(self, specialist_id: str, plan_type: str, 
                                  payment_id: str, amount_paid: int) -> SubscriptionResponse:
        """Активировать подписку после успешной оплаты"""
        subscription = await self.get_current_subscription(specialist_id)
        
        if not subscription:
            raise ValueError("Подписка не найдена")

        # Получаем информацию о плане из базы данных
        plan_info = await self.get_plan_info(plan_type)
        if not plan_info:
            raise ValueError(f"План подписки '{plan_type}' не найден")

        # Обновляем подписку
        subscription.plan_type = plan_type
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.start_date = datetime.now(timezone.utc)
        subscription.end_date = subscription.start_date + timedelta(
            days=plan_info.duration_days
        )
        subscription.payment_id = payment_id
        subscription.amount_paid = amount_paid

        await self.db.commit()
        await self.db.refresh(subscription)

        return SubscriptionResponse.model_validate(subscription)

    async def has_access(self, specialist_id: str) -> bool:
        """Проверить, есть ли у специалиста доступ к функциям"""
        status = await self.check_subscription_status(specialist_id)
        return status.has_active_subscription or status.is_trial_active

