from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services import AppointmentService
from .deps import require_auth
from ..schemas.appointments import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse, 
     AppointmentRescheduleRequest, AppointmentCancelRequest
)
from ..services.telegram_bot import send_telegram_notification

router = APIRouter(prefix="/appointments", tags=["appointments"])


#Получить записи пользователя или специалиста
@router.post("/", response_model=List[AppointmentResponse], dependencies=[Depends(require_auth)])
async def get_appointments(
    request: AppointmentCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        appointment_service = AppointmentService(db)
        return await appointment_service.get_appointments_by_request(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении записей: {str(e)}")

#Получить записи специалиста по ID
@router.get("/specialist/{specialist_id}", response_model=List[AppointmentResponse], dependencies=[Depends(require_auth)])
async def get_specialist_appointments(
    specialist_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        appointment_service = AppointmentService(db)
        return await appointment_service.get_specialist_appointments(specialist_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении записей специалиста: {str(e)}")
 
#Получить записи по client_id    
@router.get("/client/{client_id}", response_model=List[AppointmentResponse], dependencies=[Depends(require_auth)])
async def get_client_appointments(
    client_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        appointment_service = AppointmentService(db)
        return await appointment_service.get_client_appointments(client_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении записей: {str(e)}")    


#Получить запись по ID
@router.get("/{appointment_id}", response_model=AppointmentResponse, dependencies=[Depends(require_auth)])
async def get_appointment_by_id(
    appointment_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        appointment_service = AppointmentService(db)
        appointment = await appointment_service.get_appointment_by_id(appointment_id)
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        
        return appointment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении записи: {str(e)}")

#Получить существующие записи специалиста на определенную дату
@router.get("/", response_model=List[dict], dependencies=[Depends(require_auth)])
async def get_existing_appointments(
    specialist_id: str = Query(..., description="ID специалиста"),
    date: str = Query(..., description="Дата"),
    db: AsyncSession = Depends(get_db)
):
    try:
        appointment_service = AppointmentService(db)
        return await appointment_service.get_existing_appointments(specialist_id, date)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка при получении записей")


#Удалить запись
@router.delete("/{appointment_id}", dependencies=[Depends(require_auth)])
async def delete_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        appointment_service = AppointmentService(db)
        await appointment_service.delete_appointment(appointment_id)
        return {"message": "Запись успешно удалена"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении записи: {str(e)}")


#Создать новую запись
@router.post("/create", response_model=AppointmentResponse, dependencies=[Depends(require_auth)])
async def create_appointment(
    appointment: AppointmentCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        appointment_service = AppointmentService(db)
        return await appointment_service.create_appointment(appointment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании записи: {str(e)}")


#Перезаписать запись
@router.put("/{appointment_id}/reschedule", response_model=AppointmentResponse, dependencies=[Depends(require_auth)])
async def reschedule_appointment(
    appointment_id: int,
    reschedule_data: AppointmentRescheduleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Перезаписать запись на новое время"""
    try:
        print(f"Получены данные для перезаписи записи {appointment_id}:")
        print(f"  new_date: {reschedule_data.new_date}")
        print(f"  new_time: {reschedule_data.new_time}")
        print(f"  reason: {reschedule_data.reason}")
        print(f"  first_name: {reschedule_data.first_name}")
        print(f"  last_name: {reschedule_data.last_name}")
        print(f"  phone: {reschedule_data.phone}")
        print(f"  service_id: {reschedule_data.service_id}")
        print(f"  service_name: {reschedule_data.service_name}")
        print(f"  service_valuta: {reschedule_data.service_valuta}")
        print(f"  service_price: {reschedule_data.service_price}")
        
        appointment_service = AppointmentService(db)
        return await appointment_service.reschedule_appointment(appointment_id, reschedule_data)
    except ValueError as e:
        print(f"Ошибка валидации: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Ошибка при переносе записи: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при переносе записи: {str(e)}")


#Отменить запись
@router.put("/{appointment_id}/cancel", dependencies=[Depends(require_auth)])
async def cancel_appointment(
    appointment_id: int,
    cancel_data: AppointmentCancelRequest,
    db: AsyncSession = Depends(get_db)
):
    """Отменить запись"""
    try:
        appointment_service = AppointmentService(db)
        await appointment_service.cancel_appointment(appointment_id, cancel_data)
        return {"message": "Запись успешно отменена"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при отмене записи: {str(e)}")
