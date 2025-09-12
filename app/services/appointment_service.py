from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from ..models.appointments import Appointments, AppointmentServices
from ..models.specialist import Specialist
from ..schemas.appointments import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse, 
    AppointmentRescheduleRequest, AppointmentCancelRequest
)
from ..services.telegram_bot import send_telegram_notification
import logging

logger = logging.getLogger(__name__)


class AppointmentService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def _find_specialist_chat_id(self, specialist_user_id: str) -> Optional[str]:
        try:
            result = await self.db.execute(
                select(Specialist.chat_id).where(Specialist.user_id == specialist_user_id)
            )
            chat_id = result.scalar_one_or_none()
            return chat_id
        except Exception as e:
            logger.error(f"Ошибка при получении chat_id специалиста {specialist_user_id}: {e}")
            return None
    
    async def get_appointment_by_id(self, appointment_id: int) -> Optional[Appointments]:
        try:
            result = await self.db.execute(
                select(Appointments).where(Appointments.id == appointment_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении записи {appointment_id}: {e}")
            raise
    
    async def get_user_appointments(self, client_id: str) -> List[Appointments]:
        try:
            result = await self.db.execute(
                select(Appointments).where(Appointments.client_id == client_id)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении записей пользователя {client_id}: {e}")
            raise
    
    async def get_specialist_appointments(self, specialist_id: str) -> List[Appointments]:
        try:
            result = await self.db.execute(
                select(Appointments).where(Appointments.specialist_id == specialist_id)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении записей специалиста {specialist_id}: {e}")
            raise
        
    async def get_client_appointments(self, client_id: str) -> List[Appointments]:
        try:
            result = await self.db.execute(
                select(Appointments).where(Appointments.client_id == client_id)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении записей {client_id}: {e}")
            raise    
    
    async def get_existing_appointments(self, specialist_id: str, date: str) -> List[dict]:
        try:
            result = await self.db.execute(
                select(Appointments.time).where(
                    and_(
                        Appointments.specialist_id == specialist_id,
                        Appointments.date == date,
                        Appointments.status == "active"
                    )
                )
            )
            appointments = result.scalars().all()
            return [{"time": time} for time in appointments]
        except Exception as e:
            logger.error(f"Ошибка при получении существующих записей: {e}")
            raise
    
    async def create_appointment(self, appointment_data: AppointmentCreate) -> Appointments:
        try:
            db_appointment = Appointments(**appointment_data.dict())
            self.db.add(db_appointment)
            await self.db.commit()
            await self.db.refresh(db_appointment)
            logger.info(f"Запись {db_appointment.id} успешно создана")

            # Красивые уведомления клиенту и специалисту
            try:
                price = (db_appointment.service_price or "").strip()
                valuta = (db_appointment.service_valuta or "").strip()
                price_line = f" {price} {valuta}".strip() if price or valuta else ""

                # Клиенту
                client_message = (
                    f"<b>✅ Запись создана</b>\n\n"
                    f"🗓️ <b>Дата:</b> {db_appointment.date}\n"
                    f"⏰ <b>Время:</b> {db_appointment.time}\n"
                    f"💇 <b>Услуга:</b> {db_appointment.service_name or '-'}{price_line}\n"
                    f"👤 <b>Специалист:</b> {db_appointment.specialist_name or ''} {db_appointment.specialist_last_name or ''}\n"
                    f"📍 <b>Адрес:</b> {db_appointment.specialist_address or '-'}\n"
                    f"📞 <b>Телефон:</b> {db_appointment.specialist_phone or '-'}"
                )
                await send_telegram_notification(client_message, db_appointment.client_id)

                # Специалисту
                specialist_chat_id = await self._find_specialist_chat_id(db_appointment.specialist_id)
                if specialist_chat_id:
                    specialist_message = (
                        f"<b>🆕 Новая запись</b>\n\n"
                        f"🗓️ <b>Дата:</b> {db_appointment.date}\n"
                        f"⏰ <b>Время:</b> {db_appointment.time}\n"
                        f"🙍 <b>Клиент:</b> {db_appointment.first_name} {db_appointment.last_name}\n"
                        f"📞 <b>Телефон:</b> {db_appointment.phone}\n"
                        f"💇 <b>Услуга:</b> {db_appointment.service_name or '-'}{price_line}"
                    )
                    await send_telegram_notification(specialist_message, specialist_chat_id)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомления о создании записи {db_appointment.id}: {e}")
            return db_appointment
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при создании записи: {e}")
            raise
    
    async def delete_appointment(self, appointment_id: int) -> bool:
        try:
            appointment = await self.get_appointment_by_id(appointment_id)
            if not appointment:
                raise ValueError(f"Запись {appointment_id} не найдена")
            
            await self.db.delete(appointment)
            await self.db.commit()
            logger.info(f"Запись {appointment_id} успешно удалена")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при удалении записи {appointment_id}: {e}")
            raise
    
    async def get_appointments_by_request(self, request: AppointmentCreate) -> List[Appointments]:
        try:
            if request.specialist_id:
                return await self.get_specialist_appointments(request.specialist_id)
            else:
                return await self.get_user_appointments(request.client_id)
        except Exception as e:
            logger.error(f"Ошибка при получении записей по запросу: {e}")
            raise
    
    async def reschedule_appointment(self, appointment_id: int, reschedule_data: AppointmentRescheduleRequest) -> Appointments:
        """Перезаписать запись на новое время"""
        try:
            appointment = await self.get_appointment_by_id(appointment_id)
            if not appointment:
                raise ValueError(f"Запись {appointment_id} не найдена")
            
            if appointment.status != "active":
                raise ValueError(f"Нельзя перезаписать запись со статусом {appointment.status}")
            
            # Обновляем запись (без проверки свободного времени)
            appointment.date = reschedule_data.new_date
            appointment.time = reschedule_data.new_time
            # Статус остается active при перезаписи
            
            # Обновляем дополнительные поля если они переданы
            if reschedule_data.first_name is not None:
                appointment.first_name = reschedule_data.first_name
            if reschedule_data.last_name is not None:
                appointment.last_name = reschedule_data.last_name
            if reschedule_data.phone is not None:
                appointment.phone = reschedule_data.phone
            if reschedule_data.service_id is not None:
                appointment.service_id = reschedule_data.service_id
            if reschedule_data.service_name is not None:
                appointment.service_name = reschedule_data.service_name
            if reschedule_data.service_valuta is not None:
                appointment.service_valuta = reschedule_data.service_valuta
            if reschedule_data.service_price is not None:
                appointment.service_price = reschedule_data.service_price
            
            await self.db.commit()
            await self.db.refresh(appointment)
            
            # Отправляем красивые уведомления
            client_message = (
                f"<b>🔄 Запись перенесена</b>\n\n"
                f"📅 <b>Новая дата:</b> {reschedule_data.new_date}\n"
                f"⏰ <b>Новое время:</b> {reschedule_data.new_time}\n"
                f"👤 <b>Специалист:</b> {appointment.specialist_name} {appointment.specialist_last_name}\n"
                f"📞 <b>Телефон:</b> {appointment.specialist_phone or '-'}\n"
                f"🏠 <b>Адрес:</b> {appointment.specialist_address or '-'}"
            )
            await send_telegram_notification(client_message, appointment.client_id)

            specialist_chat_id = await self._find_specialist_chat_id(appointment.specialist_id)
            if specialist_chat_id:
                specialist_message = (
                    f"<b>🔄 Перенос записи</b>\n\n"
                    f"📅 <b>Дата:</b> {reschedule_data.new_date}\n"
                    f"⏰ <b>Время:</b> {reschedule_data.new_time}\n"
                    f"🙍 <b>Клиент:</b> {appointment.first_name} {appointment.last_name}\n"
                    f"📞 <b>Телефон:</b> {appointment.phone}"
                )
                await send_telegram_notification(specialist_message, specialist_chat_id)
            
            logger.info(f"Запись {appointment_id} успешно перенесена")
            return appointment
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при переносе записи {appointment_id}: {e}")
            raise
    
    async def cancel_appointment(self, appointment_id: int, cancel_data: AppointmentCancelRequest) -> bool:
        """Отменить запись"""
        try:
            appointment = await self.get_appointment_by_id(appointment_id)
            if not appointment:
                raise ValueError(f"Запись {appointment_id} не найдена")
            
            if appointment.status != "active":
                raise ValueError(f"Нельзя отменить запись со статусом {appointment.status}")
            
            # Обновляем статус записи
            appointment.status = "cancelled"
            
            await self.db.commit()
            
            # Отправляем красивые уведомления
            client_message = (
                f"<b>❌ Запись отменена</b>\n\n"
                f"📅 <b>Дата:</b> {appointment.date}\n"
                f"⏰ <b>Время:</b> {appointment.time}\n"
                f"👤 <b>Специалист:</b> {appointment.specialist_name} {appointment.specialist_last_name}\n"
                f"📞 <b>Телефон:</b> {appointment.specialist_phone or '-'}\n"
                f"🏠 <b>Адрес:</b> {appointment.specialist_address or '-'}\n"
                f"📝 <b>Причина:</b> {cancel_data.reason}"
            )
            await send_telegram_notification(client_message, appointment.client_id)

            specialist_chat_id = await self._find_specialist_chat_id(appointment.specialist_id)
            if specialist_chat_id:
                specialist_message = (
                    f"<b>❌ Отмена записи</b>\n\n"
                    f"📅 <b>Дата:</b> {appointment.date}\n"
                    f"⏰ <b>Время:</b> {appointment.time}\n"
                    f"🙍 <b>Клиент:</b> {appointment.first_name} {appointment.last_name}\n"
                    f"📞 <b>Телефон:</b> {appointment.phone}\n"
                    f"📝 <b>Причина:</b> {cancel_data.reason}"
                )
                await send_telegram_notification(specialist_message, specialist_chat_id)
            
            logger.info(f"Запись {appointment_id} успешно отменена")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при отмене записи {appointment_id}: {e}")
            raise
