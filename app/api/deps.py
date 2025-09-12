from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services import UserService, SpecialistService
from ..services.auth_service import verify_session_token


async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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


async def require_specialist(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get("naznach_specialist")
    if not token:
        raise HTTPException(status_code=401, detail="Нет сессии")

    payload = verify_session_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Сессия недействительна")

    telegram_id = str(payload["sub"])
    user_service = UserService(db)
    user = await user_service.get_user_by_telegram_id(telegram_id)
    if not user or not user.is_master:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    specialist_service = SpecialistService(db)
    specialist = await specialist_service.get_specialist_by_user_id(telegram_id)
    if not specialist:
        raise HTTPException(status_code=404, detail="Специалист не найден")
    return specialist

