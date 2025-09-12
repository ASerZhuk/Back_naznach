from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services import SpecialistService, FileService
from .deps import require_auth
from ..schemas.specialist import SpecialistCreate, SpecialistUpdate, SpecialistResponse

router = APIRouter(prefix="/specialists", tags=["specialists"])


#Получить специалиста по user_id
@router.get("/{user_id}", response_model=SpecialistResponse, dependencies=[Depends(require_auth)])
async def get_specialist(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        specialist_service = SpecialistService(db)
        specialist = await specialist_service.get_specialist_by_user_id(user_id)
        
        if not specialist:
            raise HTTPException(status_code=404, detail="Специалист не найден")
        
        return specialist
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении специалиста: {str(e)}")


#Создать нового специалиста
@router.post("/", response_model=SpecialistResponse, status_code=201, dependencies=[Depends(require_auth)])
async def create_specialist(
    specialist: SpecialistCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        specialist_service = SpecialistService(db)
        return await specialist_service.create_specialist(specialist)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании специалиста: {str(e)}")


#Обновить специалиста
@router.put("/{user_id}", response_model=SpecialistResponse, dependencies=[Depends(require_auth)])
async def update_specialist(
    user_id: str,
    specialist_update: SpecialistUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        specialist_service = SpecialistService(db)
        return await specialist_service.update_specialist(user_id, specialist_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении специалиста: {str(e)}")


#Получить всех специалистов
@router.get("/", response_model=List[SpecialistResponse], dependencies=[Depends(require_auth)])
async def get_all_specialists(
    db: AsyncSession = Depends(get_db)
):
    try:
        specialist_service = SpecialistService(db)
        return await specialist_service.get_all_specialists()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении специалистов: {str(e)}")


#Загрузить изображение специалиста
@router.post("/{user_id}/image", dependencies=[Depends(require_auth)])
async def upload_specialist_image(
    user_id: str,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Загрузить изображение для специалиста"""
    try:
        specialist_service = SpecialistService(db)
        
        # Проверяем, существует ли специалист
        specialist = await specialist_service.get_specialist_by_user_id(user_id)
        if not specialist:
            raise HTTPException(status_code=404, detail="Специалист не найден")
        
        # Сохраняем изображение
        image_path = await FileService.save_image(image, user_id)
        
        # Обновляем путь к изображению в базе данных
        updated_specialist = await specialist_service.update_specialist(
            user_id, 
            SpecialistUpdate(image=image_path)
        )
        
        return {
            "message": "Изображение успешно загружено",
            "image_path": image_path,
            "specialist": updated_specialist
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке изображения: {str(e)}")


#Удалить изображение специалиста
@router.delete("/{user_id}/image", dependencies=[Depends(require_auth)])
async def delete_specialist_image(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Удалить изображение специалиста"""
    try:
        specialist_service = SpecialistService(db)
        
        # Получаем специалиста
        specialist = await specialist_service.get_specialist_by_user_id(user_id)
        if not specialist:
            raise HTTPException(status_code=404, detail="Специалист не найден")
        
        # Удаляем файл изображения если он существует
        if specialist.image:
            FileService.delete_image(specialist.image)
        
        # Обновляем запись в базе данных
        updated_specialist = await specialist_service.update_specialist(
            user_id, 
            SpecialistUpdate(image=None)
        )
        
        return {
            "message": "Изображение успешно удалено",
            "specialist": updated_specialist
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении изображения: {str(e)}")
