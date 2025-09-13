from pydantic import BaseModel
from typing import Optional


class ServiceBase(BaseModel):
    specialist_id: str
    name: str
    description: Optional[str] = None
    price: Optional[str] = None
    duration: int
    valuta: Optional[str] = None


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[str] = None
    duration: Optional[int] = None
    valuta: Optional[str] = None


class ServiceResponse(ServiceBase):
    id: int
    
    class Config:
        from_attributes = True
        orm_mode = True

