from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from ..models.specialist import Specialist
from ..schemas.specialist import SpecialistCreate, SpecialistUpdate, SpecialistResponse
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)


class SpecialistService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_specialist_by_user_id(self, user_id: str) -> Optional[Specialist]:
        """Получить специалиста по user_id"""
        try:
            result = await self.db.execute(
                select(Specialist)
                .options(
                    selectinload(Specialist.grafiks),
                    selectinload(Specialist.services),
                    selectinload(Specialist.appointments),
                )
                .where(Specialist.user_id == user_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении специалиста {user_id}: {e}")
            raise
        
    
    async def get_all_specialists(self) -> List[Specialist]:
        """Получить всех специалистов"""
        try:
            result = await self.db.execute(select(Specialist))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении всех специалистов: {e}")
            raise

    async def get_specialist_by_phone(self, phone: str) -> Optional[Specialist]:
        """Получить специалиста по номеру телефона (с учетом разных форматов хранения).

        Пытаемся сопоставить по нескольким возможным форматам: +7XXXXXXXXXX, 7XXXXXXXXXX, 8XXXXXXXXXX, XXXXXXXXXX
        """
        try:
            digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
            last10 = digits[-10:] if len(digits) >= 10 else digits
            candidates = set()
            if last10:
                candidates.add(f"+7{last10}")
                candidates.add(f"7{last10}")
                candidates.add(f"8{last10}")
                candidates.add(last10)
            # Также добавляем исходное значение как есть
            if phone:
                candidates.add(phone)

            conditions = [Specialist.phone == cand for cand in candidates]
            if not conditions:
                return None
            stmt = select(Specialist).where(or_(*conditions))
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении специалиста по телефону {phone}: {e}")
            raise
    
    
    async def create_specialist(self, specialist_data: SpecialistCreate) -> Specialist:
        """Создать нового специалиста"""
        try:
            # Проверяем, существует ли уже специалист с таким user_id
            existing_specialist = await self.get_specialist_by_user_id(specialist_data.user_id)
            if existing_specialist:
                raise ValueError(f"Специалист с user_id {specialist_data.user_id} уже существует")
            
            # Генерируем уникальную ссылку для специалиста
            telegram_link = f"https://t.me/{settings.telegram_bot_username}?start={specialist_data.user_id}"
            
            # Добавляем ссылку к данным специалиста
            specialist_dict = specialist_data.dict()
            specialist_dict['telegram_link'] = telegram_link
            
            db_specialist = Specialist(**specialist_dict)
            self.db.add(db_specialist)
            await self.db.commit()
            await self.db.refresh(db_specialist)
            logger.info(f"Специалист {specialist_data.user_id} успешно создан с ссылкой: {telegram_link}")
            return db_specialist
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при создании специалиста {specialist_data.user_id}: {e}")
            raise
    
    
    async def update_specialist(self, user_id: str, specialist_data: SpecialistUpdate) -> Specialist:
        """Обновить специалиста"""
        try:
            specialist = await self.get_specialist_by_user_id(user_id)
            if not specialist:
                raise ValueError(f"Специалист {user_id} не найден")
            
            update_data = specialist_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(specialist, field, value)
            
            await self.db.commit()
            await self.db.refresh(specialist)
            logger.info(f"Специалист {user_id} успешно обновлен")
            return specialist
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при обновлении специалиста {user_id}: {e}")
            raise
    
    
    async def create_specialist_for_user(self, user_id: str, **kwargs) -> Specialist:
        """Создать специалиста для пользователя"""
        try:
            logger.info(f"Начинаем создание специалиста для пользователя {user_id}")
            logger.info(f"Переданные данные: {kwargs}")
            
            # Проверяем, существует ли уже специалист
            existing_specialist = await self.get_specialist_by_user_id(user_id)
            if existing_specialist:
                logger.info(f"Специалист {user_id} уже существует")
                return existing_specialist
            
            # Генерируем уникальную ссылку для специалиста
            telegram_link = f"https://t.me/{settings.telegram_bot_username}?start={user_id}"
            
            # Создаем данные специалиста
            specialist_data = {
                "user_id": user_id,
                "telegram_link": telegram_link,
                **kwargs
            }
            
            logger.info(f"Создаем специалиста с данными: {specialist_data}")
            
            return await self.create_specialist(SpecialistCreate(**specialist_data))
        except Exception as e:
            logger.error(f"Ошибка при создании специалиста для пользователя {user_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
