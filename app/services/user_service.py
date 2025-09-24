from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from ..models.user import User
from ..models.specialist import Specialist
from ..models.appointments import Appointments
from ..schemas.user import UserCreate, UserUpdate, UserResponse
import logging

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_telegram_id(self, telegram_id: str) -> Optional[UserResponse]:
        """Получить пользователя по telegram_id"""
        try:
            result = await self.db.execute(
                select(User)
                .options(
                    selectinload(User.specialist)
                    .options(
                        selectinload(Specialist.grafiks),
                        selectinload(Specialist.services)
                    )
                )
                .where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            # Получить уникальных специалистов, к которым записывался пользователь
            fav_result = await self.db.execute(
                select(Specialist)
                .join(Appointments, Specialist.user_id == Appointments.specialist_id)
                .where(Appointments.client_id == str(user.telegram_id))
                .options(
                    selectinload(Specialist.grafiks),
                    selectinload(Specialist.services)
                )
            )
            favorite_specialists = list(fav_result.scalars().unique())

            # Динамически присоединяем атрибут к объекту user перед возвратом
            setattr(user, "favorite_specialists", favorite_specialists)

            return user
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя: {e}")
            return None
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Создать нового пользователя"""
        try:
            user = User(**user_data.dict())
            self.db.add(user)
            await self.db.commit()
            # Возвращаем пользователя с предзагруженными связями
            return await self.get_user_by_telegram_id(user.telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при создании пользователя: {e}")
            await self.db.rollback()
            raise
    
    async def update_user(self, telegram_id: str, user_data: UserUpdate) -> Optional[UserResponse]:
        """Обновить пользователя"""
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if not user:
                return None
            
            for field, value in user_data.dict(exclude_unset=True).items():
                setattr(user, field, value)
            
            await self.db.commit()
            # Возвращаем пользователя с предзагруженными связями
            return await self.get_user_by_telegram_id(telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при обновлении пользователя: {e}")
            await self.db.rollback()
            raise
    
    async def register_or_update_user(self, telegram_id: str, username: str = None, first_name: str = None, last_name: str = None) -> UserResponse:
        """Зарегистрировать или обновить пользователя"""
        try:
            user = await self.get_user_by_telegram_id(telegram_id) 
            
            if user:
                # Обновляем существующего пользователя
                update_data = UserUpdate(
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                return await self.update_user(telegram_id, update_data)
            else:
                # Создаем нового пользователя
                create_data = UserCreate(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                return await self.create_user(create_data)
        except Exception as e:
            logger.error(f"Ошибка при регистрации/обновлении пользователя: {e}")
            raise
    
    async def set_user_type(self, telegram_id: str, is_master: bool) -> Optional[UserResponse]:
        """Установить тип пользователя (специалист или клиент)"""
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if not user:
                return None
            
            user.is_master = is_master
            user.is_first = False  # Устанавливаем, что это не первый вход
            
            await self.db.commit()
            return await self.get_user_by_telegram_id(telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при установке типа пользователя: {e}")
            await self.db.rollback()
            raise
    
    async def mark_user_not_first(self, telegram_id: str) -> Optional[UserResponse]:
        """Отметить, что пользователь уже не первый раз заходит"""
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if not user:
                return None
            
            user.is_first = False
            await self.db.commit()
            return await self.get_user_by_telegram_id(telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при отметке пользователя: {e}")
            await self.db.rollback()
            raise
