from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from ..models.service import Service
from ..models.grafik import Grafik
from ..models.appointments import AppointmentServices
from ..schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse
import logging

logger = logging.getLogger(__name__)


class ServiceService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_service_by_id(self, service_id: int) -> Optional[Service]:
        try:
            result = await self.db.execute(
                select(Service).where(Service.id == service_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении услуги {service_id}: {e}")
            raise
    
    
    async def get_specialist_services(self, specialist_id: str) -> List[Service]:
        try:
            result = await self.db.execute(
                select(Service).where(Service.specialist_id == specialist_id)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении услуг специалиста {specialist_id}: {e}")
            raise
    
    
    async def create_service(self, service_data: ServiceCreate) -> Service:
        try:
            result = await self.db.execute(
                select(Grafik).where(Grafik.specialist_id == service_data.specialist_id)
            )
            grafiks = result.scalars().all()
            
            if not grafiks:
                raise ValueError(f"График для специалиста {service_data.specialist_id} не найден")
            
            db_service = Service(**service_data.dict())
            self.db.add(db_service)
            await self.db.commit()
            await self.db.refresh(db_service)
            logger.info(f"Услуга для специалиста {service_data.specialist_id} успешно создана")
            return db_service
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при создании услуги: {e}")
            raise
    
    
    async def update_service(self, service_id: int, service_data: ServiceUpdate) -> Service:
        try:
            service = await self.get_service_by_id(service_id)
            if not service:
                raise ValueError(f"Услуга {service_id} не найдена")
            
            update_data = service_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(service, field, value)
            
            await self.db.commit()
            await self.db.refresh(service)
            logger.info(f"Услуга {service_id} успешно обновлена")
            return service
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при обновлении услуги {service_id}: {e}")
            raise
    
    
    async def delete_service(self, service_id: int) -> bool:
        try:
            service = await self.get_service_by_id(service_id)
            if not service:
                raise ValueError(f"Услуга {service_id} не найдена")
            
            # Проверка наличия записей перед удалением
            result = await self.db.execute(
                select(AppointmentServices).where(AppointmentServices.service_id == service_id)
            )
            appointment_services = result.scalars().all()
            
            # Удаляем все связанные записи, если они есть
            if appointment_services:
                for apt_service in appointment_services:
                    await self.db.delete(apt_service)
                logger.info(f"Удалено {len(appointment_services)} связанных записей для услуги {service_id}")
            
            await self.db.delete(service)
            await self.db.commit()
            logger.info(f"Услуга {service_id} успешно удалена")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при удалении услуги {service_id}: {e}")
            raise
