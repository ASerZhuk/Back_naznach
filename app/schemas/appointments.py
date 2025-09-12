from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AppointmentBase(BaseModel):
    client_id: str
    first_name: str
    last_name: str
    specialist_id: str
    service_id: Optional[int] = None
    service_name: Optional[str] = None
    service_valuta: Optional[str] = None
    date: str
    time: str
    phone: str
    specialist_name: Optional[str] = None
    specialist_last_name: Optional[str] = None
    specialist_address: Optional[str] = None
    service_price: Optional[str] = None
    specialist_phone: Optional[str] = None
    status: Optional[str] = "active"


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    service_id: Optional[int] = None
    service_name: Optional[str] = None
    service_valuta: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    phone: Optional[str] = None
    specialist_name: Optional[str] = None
    specialist_last_name: Optional[str] = None
    specialist_address: Optional[str] = None
    service_price: Optional[str] = None
    specialist_phone: Optional[str] = None
    status: Optional[str] = None


class AppointmentRescheduleRequest(BaseModel):
    new_date: str
    new_time: str
    reason: Optional[str] = None
    # Дополнительные поля для обновления записи
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    service_id: Optional[int] = None
    service_name: Optional[str] = None
    service_valuta: Optional[str] = None
    service_price: Optional[str] = None


class AppointmentCancelRequest(BaseModel):
    reason: str


class AppointmentResponse(AppointmentBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True



