import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from ..core.database import get_db
from ..services.specialist_auth_service import SpecialistAuthService
from ..services import create_session_token, verify_session_token, send_telegram_message
from ..services import UserService, SpecialistService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/specialist", tags=["specialist-auth"]) 


class RequestCodeDTO(BaseModel):
    phone: str


class VerifyCodeDTO(BaseModel):
    phone: str
    code: str


COOKIE_NAME = "naznach_specialist"


@router.post("/request-code")
async def request_code(dto: RequestCodeDTO, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        auth = SpecialistAuthService(db)
        ok, _ = await auth.request_code(dto.phone, ip=request.client.host if request.client else None)
        if not ok:
            return {
                "sent": False,
                "message": "Специалист с таким телефоном не найден. Откройте бота для регистрации.",
            }
        return {"sent": True}
    except Exception as e:
        logger.error(f"Ошибка /request-code: {e}")
        raise HTTPException(status_code=500, detail="Ошибка отправки кода")


@router.post("/verify-code")
async def verify_code(dto: VerifyCodeDTO, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        auth = SpecialistAuthService(db)
        specialist = await auth.verify_code(dto.phone, dto.code)
        if not specialist:
            raise HTTPException(status_code=401, detail="Неверный или просроченный код")

        # Создаем отдельный токен для специалистов
        token = create_session_token(str(specialist.user_id))
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
        )

        # Уведомляем в Telegram о входе (с именем и временем)
        chat_id = specialist.chat_id or specialist.user_id
        if chat_id:
            try:
                full_name = f"{(specialist.first_name or '').strip()} {(specialist.last_name or '').strip()}".strip()
                ts = datetime.now().strftime('%d.%m.%Y %H:%M')
                text = (
                    f"✅ Вход в админ‑панель\n"
                    f"👤 {full_name or 'Специалист'}\n"
                    f"🕒 {ts}"
                )
                await send_telegram_message(chat_id=str(chat_id), text=text)
            except Exception:
                pass

        return {"message": "Успешный вход", "specialist_id": specialist.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка /verify-code: {e}")
        raise HTTPException(status_code=500, detail="Ошибка подтверждения кода")


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        token = request.cookies.get(COOKIE_NAME)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка /me: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения специалиста")


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Вышли из системы"}


