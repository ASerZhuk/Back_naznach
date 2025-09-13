from pydantic import BaseModel, Field, validator
from typing import Optional, List


class WorkScheduleBase(BaseModel):
    """Базовая схема для графика рабочего времени"""
    specialist_id: str
    day_of_week: Optional[int] = Field(None, ge=1, le=7, description="День недели: 1-понедельник, 7-воскресенье")
    specific_date: Optional[str] = Field(None, description="Конкретная дата в формате DD.MM.YYYY")
    start_time: str = Field(..., description="Время начала рабочего дня (например: 09:00)")
    end_time: str = Field(..., description="Время окончания рабочего дня (например: 18:00)")
    grafik_name: Optional[str] = None

    @validator('day_of_week', 'specific_date')
    def validate_day_or_date(cls, v, values):
        """Проверяет, что указан либо день недели, либо конкретная дата"""
        if 'day_of_week' in values and 'specific_date' in values:
            if values['day_of_week'] is None and values['specific_date'] is None:
                raise ValueError('Должен быть указан либо день недели, либо конкретная дата')
        return v

    @validator('specific_date')
    def validate_date_format(cls, v):
        """Проверяет формат даты DD.MM.YYYY"""
        if not v:
            return v
        try:
            parts = v.split('.')
            if len(parts) != 3:
                raise ValueError
            day, month, year = map(int, parts)
            if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100):
                raise ValueError
        except ValueError:
            raise ValueError('Дата должна быть в формате DD.MM.YYYY (например: 15.12.2024)')
        return v

    @validator('start_time', 'end_time')
    def validate_time_format(cls, v):
        """Проверяет формат времени HH:MM"""
        if not v:
            return v
        try:
            hours, minutes = map(int, v.split(':'))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError
        except ValueError:
            raise ValueError('Время должно быть в формате HH:MM (например: 09:00)')
        return v

    @validator('end_time')
    def validate_end_time(cls, v, values):
        """Проверяет, что время окончания больше времени начала"""
        if 'start_time' in values and v and values['start_time']:
            if v <= values['start_time']:
                raise ValueError('Время окончания должно быть больше времени начала')
        return v


class AvailableSlotsBase(BaseModel):
    """Базовая схема для графика доступных временных слотов"""
    specialist_id: str
    day_of_week: Optional[int] = Field(None, ge=1, le=7, description="День недели: 1-понедельник, 7-воскресенье")
    specific_date: Optional[str] = Field(None, description="Конкретная дата в формате DD.MM.YYYY")
    time_slots: List[str] = Field(..., description="Список временных слотов (например: ['09:00', '10:00', '14:00'])")
    grafik_name: Optional[str] = None

    @validator('day_of_week', 'specific_date')
    def validate_day_or_date(cls, v, values):
        """Проверяет, что указан либо день недели, либо конкретная дата"""
        if 'day_of_week' in values and 'specific_date' in values:
            if values['day_of_week'] is None and values['specific_date'] is None:
                raise ValueError('Должен быть указан либо день недели, либо конкретная дата')
        return v

    @validator('specific_date')
    def validate_date_format(cls, v):
        """Проверяет формат даты DD.MM.YYYY"""
        if not v:
            return v
        try:
            parts = v.split('.')
            if len(parts) != 3:
                raise ValueError
            day, month, year = map(int, parts)
            if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100):
                raise ValueError
        except ValueError:
            raise ValueError('Дата должна быть в формате DD.MM.YYYY (например: 15.12.2024)')
        return v

    @validator('time_slots')
    def validate_time_slots(cls, v):
        """Проверяет формат временных слотов"""
        if not v:
            raise ValueError('Должен быть указан хотя бы один временной слот')
        
        for time_slot in v:
            try:
                hours, minutes = map(int, time_slot.split(':'))
                if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                    raise ValueError
            except ValueError:
                raise ValueError(f'Неверный формат времени: {time_slot}. Используйте формат HH:MM')
        
        # Проверяем, что слоты отсортированы по времени
        sorted_slots = sorted(v)
        if v != sorted_slots:
            raise ValueError('Временные слоты должны быть отсортированы по времени')
        
        return v


class GrafikBase(BaseModel):
    """Базовая схема для графика (общая)"""
    specialist_id: str
    day_of_week: Optional[int] = Field(None, ge=1, le=7, description="День недели: 1-понедельник, 7-воскресенье")
    specific_date: Optional[str] = Field(None, description="Конкретная дата в формате DD.MM.YYYY")
    grafik_type: str = Field(..., description="Тип графика: work_schedule или available_slots")
    
    # Для графика рабочего времени
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    # Для графика доступных слотов
    time_slots: Optional[List[str]] = None
    
    grafik_name: Optional[str] = None


class WorkScheduleCreate(WorkScheduleBase):
    """Схема для создания графика рабочего времени"""
    pass


class WorkScheduleUpdate(BaseModel):
    """Схема для обновления графика рабочего времени"""
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    specific_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    grafik_name: Optional[str] = None


class AvailableSlotsCreate(AvailableSlotsBase):
    """Схема для создания графика доступных слотов"""
    pass


class AvailableSlotsUpdate(BaseModel):
    """Схема для обновления графика доступных слотов"""
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    specific_date: Optional[str] = None
    time_slots: Optional[List[str]] = None
    grafik_name: Optional[str] = None


class GrafikCreate(GrafikBase):
    """Схема для создания графика (общая)"""
    pass


class GrafikUpdate(BaseModel):
    """Схема для обновления графика (общая)"""
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    grafik_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    time_slots: Optional[List[str]] = None
    grafik_name: Optional[str] = None


class WorkScheduleResponse(WorkScheduleBase):
    """Схема ответа для графика рабочего времени"""
    id: int
    
    class Config:
        from_attributes = True
        orm_mode = True



class AvailableSlotsResponse(AvailableSlotsBase):
    """Схема ответа для графика доступных слотов"""
    id: int
    
    class Config:
        from_attributes = True
        orm_mode = True



class GrafikResponse(GrafikBase):
    """Схема ответа для графика (общая)"""
    id: int
    
    class Config:
        from_attributes = True
        orm_mode = True

