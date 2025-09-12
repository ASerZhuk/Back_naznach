from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services import ServiceService
from .deps import require_auth
from ..schemas.service import ServiceCreate, ServiceUpdate, ServiceResponse

router = APIRouter(prefix="/services", tags=["services"])


#Создать новую услугу
@router.post("/", response_model=ServiceResponse, status_code=201, dependencies=[Depends(require_auth)])
async def create_service(
    service: ServiceCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        service_service = ServiceService(db)
        return await service_service.create_service(service)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании услуги: {str(e)}")


#Удалить услугу
@router.delete("/{service_id}", dependencies=[Depends(require_auth)])
async def delete_service(
    service_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        service_service = ServiceService(db)
        await service_service.delete_service(service_id)
        return {"message": "Услуга успешно удалена"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении услуги: {str(e)}")


#Обновить услугу
@router.put("/{service_id}", response_model=ServiceResponse, dependencies=[Depends(require_auth)])
async def update_service(
    service_id: int,
    service_update: ServiceUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        service_service = ServiceService(db)
        return await service_service.update_service(service_id, service_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении услуги: {str(e)}")


#Получить услуги специалиста
@router.get("/specialist/{specialist_id}", response_model=List[ServiceResponse], dependencies=[Depends(require_auth)])
async def get_specialist_services(
    specialist_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        service_service = ServiceService(db)
        return await service_service.get_specialist_services(specialist_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении услуг: {str(e)}")
    
    
#Получить услугу по ID
@router.get("/{service_id}", response_model=ServiceResponse, dependencies=[Depends(require_auth)])
async def get_service_by_id(
    service_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        service_service = ServiceService(db)
        service = await service_service.get_service_by_id(service_id)
        if not service:
            raise HTTPException(status_code=404, detail=f"Услуга {service_id} не найдена")
        return service
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении услуги: {str(e)}")    
