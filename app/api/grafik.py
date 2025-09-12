from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services import GrafikService
from .deps import require_auth
from ..schemas.grafik import (
    GrafikCreate, GrafikUpdate, GrafikResponse,
    WorkScheduleCreate, WorkScheduleUpdate, WorkScheduleResponse,
    AvailableSlotsCreate, AvailableSlotsUpdate, AvailableSlotsResponse
)

router = APIRouter(prefix="/grafik", tags=["grafik"])


# Свободные слоты на дату (должен быть ПЕРЕД /{specialist_id})
@router.get("/available-time", dependencies=[Depends(require_auth)])
async def get_available_time(
    specialist_id: str = Query(..., description="ID специалиста"),
    date: str = Query(..., description="Дата в формате DD.MM.YYYY"),
    day_of_week: int | None = Query(None, description="День недели: 1-понедельник, 7-воскресенье"),
    service_duration: int | None = Query(None, description="Длительность услуги в минутах"),
    db: AsyncSession = Depends(get_db)
):
    """Получить свободные временные слоты на выбранную дату, исключая занятые записи."""
    print(f"API вызван с параметрами: specialist_id={specialist_id}, date={date}, day_of_week={day_of_week}")
    try:
        grafik_service = GrafikService(db)
        free_slots = await grafik_service.get_available_time_slots(specialist_id, date, day_of_week, service_duration)
        print(f"API возвращает слоты: {free_slots}")
        print(f"Тип возвращаемых данных: {type(free_slots)}")
        return free_slots
    except Exception as e:
        print(f"Ошибка в API: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка при получении свободных слотов: {str(e)}")

# Получить график специалиста по типу
@router.get("/{specialist_id}", response_model=List[GrafikResponse], dependencies=[Depends(require_auth)])
async def get_specialist_grafik(
    specialist_id: str,
    grafik_type: str = Query(None, description="Тип графика: work_schedule, available_slots или все"),
    specific_date: str = Query(None, description="Конкретная дата в формате DD.MM.YYYY"),
    db: AsyncSession = Depends(get_db)
):
    """Получить график специалиста"""
    try:
        grafik_service = GrafikService(db)
        return await grafik_service.get_specialist_grafik(specialist_id, grafik_type, specific_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении графика: {str(e)}")


# Создать график рабочего времени
@router.post("/work-schedule", response_model=WorkScheduleResponse, status_code=201, dependencies=[Depends(require_auth)])
async def create_work_schedule(
    work_schedule: WorkScheduleCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать график рабочего времени для специалиста"""
    try:
        grafik_service = GrafikService(db)
        return await grafik_service.create_work_schedule(work_schedule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании графика: {str(e)}")


# Создать график доступных слотов
@router.post("/available-slots", response_model=AvailableSlotsResponse, status_code=201, dependencies=[Depends(require_auth)])
async def create_available_slots(
    available_slots: AvailableSlotsCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать график доступных временных слотов для специалиста"""
    try:
        grafik_service = GrafikService(db)
        return await grafik_service.create_available_slots(available_slots)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании графика: {str(e)}")


# Обновить график рабочего времени
@router.put("/work-schedule/{grafik_id}", response_model=WorkScheduleResponse, dependencies=[Depends(require_auth)])
async def update_work_schedule(
    grafik_id: int,
    work_schedule_update: WorkScheduleUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить график рабочего времени"""
    try:
        grafik_service = GrafikService(db)
        return await grafik_service.update_work_schedule(grafik_id, work_schedule_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении графика: {str(e)}")


# Обновить график доступных слотов
@router.put("/available-slots/{grafik_id}", response_model=AvailableSlotsResponse, dependencies=[Depends(require_auth)])
async def update_available_slots(
    grafik_id: int,
    available_slots_update: AvailableSlotsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить график доступных временных слотов"""
    try:
        grafik_service = GrafikService(db)
        return await grafik_service.update_available_slots(grafik_id, available_slots_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении графика: {str(e)}")


# Удалить график
@router.delete("/{grafik_id}", dependencies=[Depends(require_auth)])
async def delete_grafik(
    grafik_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Удалить график"""
    try:
        grafik_service = GrafikService(db)
        await grafik_service.delete_grafik(grafik_id)
        return {"message": "График успешно удален"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении графика: {str(e)}")


# Получить график по ID
@router.get("/by-id/{grafik_id}", response_model=GrafikResponse, dependencies=[Depends(require_auth)])
async def get_grafik_by_id(
    grafik_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить график по ID"""
    try:
        grafik_service = GrafikService(db)
        grafik = await grafik_service.get_grafik_by_id(grafik_id)
        if not grafik:
            raise HTTPException(status_code=404, detail="График не найден")
        return grafik
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении графика: {str(e)}")


# Тестовый эндпоинт
@router.get("/test", dependencies=[Depends(require_auth)])
async def test_endpoint():
    print("Тестовый эндпоинт вызван!")
    return {"message": "Test endpoint works"}
