import logging
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..core.database import get_db
from ..services import UserService, SpecialistService
from ..services.auth_service import (
    verify_telegram_init_data,
    create_session_token,
    verify_session_token,
)
from ..schemas.user import UserCreate, UserUpdate, UserResponse
from ..schemas.specialist import SpecialistCreate, SpecialistResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class UserRegistrationRequest(BaseModel):
    telegram_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None


class UserTypeRequest(BaseModel):
    telegram_id: str
    is_master: bool
    specialist_data: Optional[SpecialistCreate] = None
# Новые модели запросов/ответов для WebApp авторизации
class WebAppLoginRequest(BaseModel):
    initData: str


class MeResponse(UserResponse):
    pass


#Регистрация нового пользователя
@router.post("/register", response_model=UserResponse)
async def register_user(
    request: UserRegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"Начинаем регистрацию пользователя: {request.telegram_id}")
        
        user_service = UserService(db)
        user = await user_service.register_or_update_user(
            telegram_id=request.telegram_id,
            first_name=request.first_name,
            last_name=request.last_name,
            username=request.username
        )
        
        return user
    except Exception as e:
        import traceback
        logger.error(f"Ошибка при регистрации: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Ошибка при регистрации: {str(e)}")


#Установка типа пользователя (специалист/клиент)
@router.post("/set-user-type")
async def set_user_type(
    user_type_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Установить тип пользователя (специалист или клиент)"""
    try:
        telegram_id = user_type_data.get("telegram_id")
        is_master = user_type_data.get("is_master", False)
        specialist_data = user_type_data.get("specialist_data")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="telegram_id обязателен")
        
        logger.info(f"Устанавливаем тип пользователя {telegram_id}: is_master={is_master}")
        
        user_service = UserService(db)
        specialist_service = SpecialistService(db)

        # Устанавливаем тип пользователя
        user = await user_service.set_user_type(telegram_id, is_master)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Если это специалист, создаем запись в таблице specialist
        if is_master and specialist_data:
            try:
                logger.info(f"Создаем специалиста для пользователя {telegram_id}")
                logger.info(f"Данные специалиста: {specialist_data}")
                
                specialist = await specialist_service.create_specialist_for_user(
                    user_id=telegram_id,
                    **specialist_data
                )
                logger.info(f"Специалист создан для пользователя {telegram_id}: {specialist}")
            except Exception as e:
                logger.error(f"Ошибка при создании специалиста: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Не прерываем процесс, если не удалось создать специалиста
        else:
            logger.info(f"Пользователь {telegram_id} не специалист или нет данных специалиста")
        
        return {
            "message": "Тип пользователя успешно установлен",
            "user": user,
            "is_master": is_master
        }
        
    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при установке типа пользователя: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


#Получение пользователя по Telegram ID
@router.get("/user/{telegram_id}", response_model=UserResponse)
async def get_user_by_telegram_id(
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


# WebApp Login: принимает initData, проверяет подпись и устанавливает cookie-сессию
@router.post("/telegram-webapp/login", response_model=UserResponse)
async def telegram_webapp_login(
    data: WebAppLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    try:
        ok, user_obj, err = verify_telegram_init_data(data.initData)
        if not ok or not user_obj:
            raise HTTPException(status_code=401, detail=err or "Неверные данные авторизации")

        telegram_id = str(user_obj.get("id"))
        username = user_obj.get("username")
        first_name = user_obj.get("first_name")
        last_name = user_obj.get("last_name")

        user_service = UserService(db)
        user = await user_service.register_or_update_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

        # Сессионный cookie: не задаем max-age, токен все еще со сроком действия
        token = create_session_token(telegram_id, expires_in_seconds=60 * 60 * 24 * 7)

        # Устанавливаем HttpOnly cookie
        response.set_cookie(
            key="naznach_session",
            value=token,
            httponly=True,
            secure=False,  # в проде переключить на True
            samesite="lax",  # в проде можно None + Secure
            path="/",
        )

        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка WebApp login: {e}")
        raise HTTPException(status_code=500, detail="Ошибка авторизации")


# Текущий пользователь из cookie
@router.get("/me", response_model=MeResponse)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        token = request.cookies.get("naznach_session")
        if not token:
            raise HTTPException(status_code=401, detail="Нет сессии")

        payload = verify_session_token(token)
        if not payload or not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Сессия недействительна")

        telegram_id = str(payload["sub"])
        user_service = UserService(db)
        user = await user_service.get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка /me: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения пользователя")


# Выход — удаление cookie
@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="naznach_session", path="/")
    return {"message": "Вышли из системы"}
