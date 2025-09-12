from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from ..models.grafik import Grafik
from ..models.appointments import Appointments
from ..schemas.grafik import (
    GrafikCreate, GrafikUpdate,
    WorkScheduleCreate, WorkScheduleUpdate,
    AvailableSlotsCreate, AvailableSlotsUpdate
)
import logging

logger = logging.getLogger(__name__)


class GrafikService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_grafik_by_id(self, grafik_id: int) -> Optional[Grafik]:
        """Получить график по ID"""
        try:
            result = await self.db.execute(
                select(Grafik).where(Grafik.id == grafik_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении графика {grafik_id}: {e}")
            raise
    
    async def get_specialist_grafik(self, specialist_id: str, grafik_type: str = None, specific_date: str = None) -> List[Grafik]:
        """Получить график специалиста"""
        try:
            query = select(Grafik).where(Grafik.specialist_id == specialist_id)
            
            if grafik_type:
                query = query.where(Grafik.grafik_type == grafik_type)
            
            if specific_date:
                query = query.where(Grafik.specific_date == specific_date)
            
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении графика специалиста {specialist_id}: {e}")
            raise
    
    async def create_work_schedule(self, work_schedule_data: WorkScheduleCreate) -> Grafik:
        """Создать график рабочего времени"""
        try:
            # Проверяем, существует ли уже график для этого дня недели или конкретной даты
            existing_grafik = await self._get_grafik_by_day_date_and_type(
                work_schedule_data.specialist_id,
                work_schedule_data.day_of_week,
                work_schedule_data.specific_date,
                "work_schedule"
            )
            
            if existing_grafik:
                if work_schedule_data.specific_date:
                    raise ValueError(f"График рабочего времени для даты {work_schedule_data.specific_date} уже существует")
                else:
                    raise ValueError(f"График рабочего времени для дня {work_schedule_data.day_of_week} уже существует")
            
            # Создаем новый график
            db_grafik = Grafik(
                specialist_id=work_schedule_data.specialist_id,
                day_of_week=work_schedule_data.day_of_week,
                specific_date=work_schedule_data.specific_date,
                grafik_type="work_schedule",
                start_time=work_schedule_data.start_time,
                end_time=work_schedule_data.end_time,
                grafik_name=work_schedule_data.grafik_name or (
                    f"Рабочий день {work_schedule_data.specific_date}" if work_schedule_data.specific_date 
                    else f"Рабочий день {work_schedule_data.day_of_week}"
                )
            )
            
            self.db.add(db_grafik)
            await self.db.commit()
            await self.db.refresh(db_grafik)
            
            logger.info(f"График рабочего времени создан для специалиста {work_schedule_data.specialist_id}")
            return db_grafik
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при создании графика рабочего времени: {e}")
            raise
    
    async def create_available_slots(self, available_slots_data: AvailableSlotsCreate) -> Grafik:
        """Создать график доступных временных слотов"""
        try:
            # Проверяем, существует ли уже график для этого дня недели или конкретной даты
            existing_grafik = await self._get_grafik_by_day_date_and_type(
                available_slots_data.specialist_id,
                available_slots_data.day_of_week,
                available_slots_data.specific_date,
                "available_slots"
            )
            
            if existing_grafik:
                if available_slots_data.specific_date:
                    raise ValueError(f"График доступных слотов для даты {available_slots_data.specific_date} уже существует")
                else:
                    raise ValueError(f"График доступных слотов для дня {available_slots_data.day_of_week} уже существует")
            
            # Создаем новый график
            db_grafik = Grafik(
                specialist_id=available_slots_data.specialist_id,
                day_of_week=available_slots_data.day_of_week,
                specific_date=available_slots_data.specific_date,
                grafik_type="available_slots",
                time_slots=available_slots_data.time_slots,
                grafik_name=available_slots_data.grafik_name or (
                    f"Доступные слоты {available_slots_data.specific_date}" if available_slots_data.specific_date 
                    else f"Доступные слоты {available_slots_data.day_of_week}"
                )
            )
            
            self.db.add(db_grafik)
            await self.db.commit()
            await self.db.refresh(db_grafik)
            
            logger.info(f"График доступных слотов создан для специалиста {available_slots_data.specialist_id}")
            return db_grafik
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при создании графика доступных слотов: {e}")
            raise
    
    async def update_work_schedule(self, grafik_id: int, work_schedule_update: WorkScheduleUpdate) -> Grafik:
        """Обновить график рабочего времени"""
        try:
            grafik = await self.get_grafik_by_id(grafik_id)
            if not grafik:
                raise ValueError(f"График {grafik_id} не найден")
            
            if grafik.grafik_type != "work_schedule":
                raise ValueError(f"График {grafik_id} не является графиком рабочего времени")
            
            # Обновляем поля
            update_data = work_schedule_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(grafik, field, value)
            
            await self.db.commit()
            await self.db.refresh(grafik)
            
            logger.info(f"График рабочего времени {grafik_id} успешно обновлен")
            return grafik
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при обновлении графика рабочего времени {grafik_id}: {e}")
            raise
    
    async def update_available_slots(self, grafik_id: int, available_slots_update: AvailableSlotsUpdate) -> Grafik:
        """Обновить график доступных временных слотов"""
        try:
            grafik = await self.get_grafik_by_id(grafik_id)
            if not grafik:
                raise ValueError(f"График {grafik_id} не найден")
            
            if grafik.grafik_type != "available_slots":
                raise ValueError(f"График {grafik_id} не является графиком доступных слотов")
            
            # Обновляем поля
            update_data = available_slots_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(grafik, field, value)
            
            await self.db.commit()
            await self.db.refresh(grafik)
            
            logger.info(f"График доступных слотов {grafik_id} успешно обновлен")
            return grafik
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при обновлении графика доступных слотов {grafik_id}: {e}")
            raise
    
    async def delete_grafik(self, grafik_id: int) -> bool:
        """Удалить график"""
        try:
            grafik = await self.get_grafik_by_id(grafik_id)
            if not grafik:
                raise ValueError(f"График {grafik_id} не найден")
            
            await self.db.delete(grafik)
            await self.db.commit()
            
            logger.info(f"График {grafik_id} успешно удален")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Ошибка при удалении графика {grafik_id}: {e}")
            raise
    
    async def _get_grafik_by_day_and_type(self, specialist_id: str, day_of_week: int, grafik_type: str) -> Optional[Grafik]:
        """Получить график по дню недели и типу для специалиста"""
        try:
            result = await self.db.execute(
                select(Grafik).where(
                    and_(
                        Grafik.specialist_id == specialist_id,
                        Grafik.day_of_week == day_of_week,
                        Grafik.grafik_type == grafik_type
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении графика по дню и типу: {e}")
            raise

    async def _get_grafik_by_day_date_and_type(self, specialist_id: str, day_of_week: Optional[int], specific_date: Optional[str], grafik_type: str) -> Optional[Grafik]:
        """Получить график по дню недели/конкретной дате и типу для специалиста"""
        try:
            if specific_date:
                # Ищем по конкретной дате
                result = await self.db.execute(
                    select(Grafik).where(
                        and_(
                            Grafik.specialist_id == specialist_id,
                            Grafik.specific_date == specific_date,
                            Grafik.grafik_type == grafik_type
                        )
                    )
                )
            else:
                # Ищем по дню недели
                result = await self.db.execute(
                    select(Grafik).where(
                        and_(
                            Grafik.specialist_id == specialist_id,
                            Grafik.day_of_week == day_of_week,
                            Grafik.grafik_type == grafik_type
                        )
                    )
                )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении графика по дню/дате и типу: {e}")
            raise

    async def get_available_time_slots(self, specialist_id: str, date: str, day_of_week: Optional[int] = None, service_duration: Optional[int] = None) -> List[str]:
        """Получить свободные временные слоты для специалиста на указанную дату."""
        try:
            # Парсим дату формата DD.MM.YYYY → получаем день недели (1=пн .. 7=вс)
            day, month, year = map(int, date.split('.'))
            from datetime import date as dt
            computed_weekday = dt(year, month, day).isoweekday()  # 1..7
            weekday = day_of_week or computed_weekday
            
            logger.info(f"Поиск слотов для specialist_id={specialist_id}, date={date}, weekday={weekday}")

            # 1. Сначала ищем график available_slots (готовые слоты)
            grafik = await self._get_grafik_by_day_date_and_type(
                specialist_id=specialist_id,
                day_of_week=None,
                specific_date=date,
                grafik_type="available_slots"
            )
            
            if not grafik:
                grafik = await self._get_grafik_by_day_date_and_type(
                    specialist_id=specialist_id,
                    day_of_week=weekday,
                    specific_date=None,
                    grafik_type="available_slots"
                )
            
            defined_slots = []
            
            if grafik and grafik.time_slots:
                # Используем готовые слоты из available_slots
                defined_slots = list(grafik.time_slots)
                logger.info(f"Найден график available_slots: {grafik}")
            else:
                # 2. Если нет available_slots, ищем work_schedule и генерируем слоты
                work_grafik = await self._get_grafik_by_day_date_and_type(
                    specialist_id=specialist_id,
                    day_of_week=None,
                    specific_date=date,
                    grafik_type="work_schedule"
                )
                
                if not work_grafik:
                    work_grafik = await self._get_grafik_by_day_date_and_type(
                        specialist_id=specialist_id,
                        day_of_week=weekday,
                        specific_date=None,
                        grafik_type="work_schedule"
                    )
                
                if work_grafik and work_grafik.start_time and work_grafik.end_time and service_duration:
                    # Генерируем слоты на основе рабочего времени и длительности услуги
                    defined_slots = self._generate_time_slots(
                        work_grafik.start_time, 
                        work_grafik.end_time, 
                        service_duration
                    )
                    logger.info(f"Найден график work_schedule: {work_grafik}, сгенерированы слоты: {defined_slots}")
                else:
                    logger.info(f"График не найден или недостаточно данных: work_grafik={work_grafik}, service_duration={service_duration}")
                    return []
            logger.info(f"Определенные слоты: {defined_slots}")

            # 2. Получаем занятые временные интервалы из appointments с длительностью услуг
            busy_intervals = await self._get_busy_time_intervals(specialist_id, date)
            logger.info(f"Занятые интервалы: {busy_intervals}")

            # 3. Фильтруем слоты с учетом пересечений
            free_slots = self._filter_overlapping_slots(defined_slots, busy_intervals, service_duration or 60)
            logger.info(f"Свободные слоты: {free_slots}")
            return free_slots
            
        except Exception as e:
            logger.error(f"Ошибка при получении свободных слотов для {specialist_id} на {date}: {e}")
            raise

    def _generate_time_slots(self, start_time: str, end_time: str, duration_minutes: int) -> List[str]:
        """Генерировать временные слоты на основе рабочего времени и длительности услуги"""
        try:
            from datetime import datetime, timedelta
            
            # Парсим время
            start_dt = datetime.strptime(start_time, "%H:%M")
            end_dt = datetime.strptime(end_time, "%H:%M")
            
            slots = []
            current_time = start_dt
            
            while current_time + timedelta(minutes=duration_minutes) <= end_dt:
                slots.append(current_time.strftime("%H:%M"))
                current_time += timedelta(minutes=duration_minutes)
            
            return slots
        except Exception as e:
            logger.error(f"Ошибка при генерации слотов: {e}")
            return []

    async def _get_busy_time_intervals(self, specialist_id: str, date: str) -> List[tuple]:
        """Получить занятые временные интервалы с учетом длительности услуг"""
        try:
            from ..models.appointments import Appointments
            from sqlalchemy.orm import selectinload
            
            # Получаем записи с услугами и их длительностью
            result = await self.db.execute(
                select(Appointments)
                .options(selectinload(Appointments.service))
                .where(
                    and_(
                        Appointments.specialist_id == specialist_id,
                        Appointments.date == date,
                    )
                )
            )
            appointments = result.scalars().all()
            
            busy_intervals = []
            for appointment in appointments:
                appointment_time = appointment.time
                
                # Получаем длительность услуги напрямую
                duration = 60  # по умолчанию 60 минут
                if appointment.service and appointment.service.duration:
                    duration = appointment.service.duration
                
                # Создаем интервал (время начала, время окончания)
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(appointment_time, "%H:%M")
                end_dt = start_dt + timedelta(minutes=duration)
                
                busy_intervals.append((
                    start_dt.strftime("%H:%M"),
                    end_dt.strftime("%H:%M")
                ))
            
            return busy_intervals
        except Exception as e:
            logger.error(f"Ошибка при получении занятых интервалов: {e}")
            return []

    def _filter_overlapping_slots(self, slots: List[str], busy_intervals: List[tuple], service_duration: int) -> List[str]:
        """Фильтровать слоты, исключая те, что пересекаются с занятыми интервалами"""
        try:
            from datetime import datetime, timedelta
            
            free_slots = []
            
            for slot_time in slots:
                # Вычисляем интервал для нового слота
                slot_start = datetime.strptime(slot_time, "%H:%M")
                slot_end = slot_start + timedelta(minutes=service_duration)
                
                # Проверяем пересечение с каждым занятым интервалом
                has_overlap = False
                for busy_start_str, busy_end_str in busy_intervals:
                    busy_start = datetime.strptime(busy_start_str, "%H:%M")
                    busy_end = datetime.strptime(busy_end_str, "%H:%M")
                    
                    # Проверяем пересечение интервалов
                    if (slot_start < busy_end and slot_end > busy_start):
                        has_overlap = True
                        break
                
                if not has_overlap:
                    free_slots.append(slot_time)
            
            return free_slots
        except Exception as e:
            logger.error(f"Ошибка при фильтрации слотов: {e}")
            return slots
