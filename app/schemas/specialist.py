from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .grafik import GrafikResponse
from .service import ServiceResponse


class SpecialistBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    image: Optional[str] = None
    phone: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None
    telegram_link: Optional[str] = None


class SpecialistCreate(SpecialistBase):
    pass


class SpecialistUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    chat_id: Optional[str] = None
    username: Optional[str] = None
    image: Optional[str] = None
    phone: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None
    telegram_link: Optional[str] = None


class SpecialistResponse(SpecialistBase):
    id: int
    created_at: datetime
    grafiks: list[GrafikResponse] = []
    services: list[ServiceResponse] = []
    
    class Config:
        from_attributes = True
        orm_mode = True

