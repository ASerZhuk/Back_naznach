from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .specialist import SpecialistResponse


class UserBase(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_master: bool = False
    is_first: bool = True


class UserCreate(UserBase):
    telegram_id: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_master: Optional[bool] = None
    is_first: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    telegram_id: str
    specialist: Optional[SpecialistResponse] = None
    favorite_specialists: list[SpecialistResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
