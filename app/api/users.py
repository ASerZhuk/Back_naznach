from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..core.database import get_db
from ..services import UserService
from .deps import require_auth
from ..schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


#Получить пользователя по Telegram ID
@router.get("/{telegram_id}", response_model=UserResponse, dependencies=[Depends(require_auth)])
async def get_user(
    telegram_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_service = UserService(db)
        user = await user_service.get_user_by_telegram_id(telegram_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении пользователя: {str(e)}")


#Создать нового пользователя
@router.post("/", response_model=UserResponse, status_code=201, dependencies=[Depends(require_auth)])
async def create_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_service = UserService(db)
        return await user_service.create_user(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании пользователя: {str(e)}")


#Обновить пользователя
@router.put("/{telegram_id}", response_model=UserResponse, dependencies=[Depends(require_auth)])
async def update_user(
    telegram_id: str,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_service = UserService(db)
        return await user_service.update_user(telegram_id, user_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении пользователя: {str(e)}")
