import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.login_code import LoginCode
from ..models.specialist import Specialist
from .specialist_service import SpecialistService
from .telegram_bot import send_telegram_message


OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60
RESEND_COOLDOWN_SECONDS = 30
MAX_VERIFY_ATTEMPTS = 5


def _normalize_phone_ru(phone: str) -> str:
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if len(digits) >= 10:
        digits = digits[-10:]
        return f"+7{digits}"
    return phone


def _generate_otp(length: int = OTP_LENGTH) -> str:
    # 6 цифр, ведущие нули допустимы
    import secrets
    n = secrets.randbelow(10 ** length)
    return str(n).zfill(length)


def _hash_code(code: str) -> str:
    # HMAC-SHA256 с secret_key
    return hmac.new(settings.secret_key.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


class SpecialistAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.specialist_service = SpecialistService(db)

    async def request_code(self, phone: str, ip: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        normalized = _normalize_phone_ru(phone)
        specialist = await self.specialist_service.get_specialist_by_phone(normalized)
        if not specialist or not specialist.user_id:
            # Нет специалиста — вернуть ссылку на бота
            return False, None

        # Проверка cooldown на повторную отправку
        now = datetime.now(timezone.utc)
        last = await self.db.execute(
            select(LoginCode).where(
                LoginCode.phone == normalized,
                LoginCode.specialist_id == specialist.id,
                LoginCode.used_at.is_(None)
            ).order_by(LoginCode.created_at.desc()).limit(1)
        )
        last_code: Optional[LoginCode] = last.scalar_one_or_none()
        if last_code and last_code.last_sent_at:
            delta = (now - last_code.last_sent_at).total_seconds()
            if delta < RESEND_COOLDOWN_SECONDS:
                # слишком рано повтор
                return True, None

        # Генерируем новый код, инвалидируем предыдущий активный
        if last_code and last_code.used_at is None:
            await self.db.execute(
                update(LoginCode)
                .where(LoginCode.id == last_code.id)
                .values(used_at=now)
            )

        code = _generate_otp()
        code_hash = _hash_code(code)
        expires_at = now + timedelta(seconds=OTP_TTL_SECONDS)
        entry = LoginCode(
            specialist_id=specialist.id,
            phone=normalized,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=0,
            last_sent_at=now,
            ip=ip,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        # Отправка кода в Telegram
        chat_id = specialist.chat_id or specialist.user_id
        if chat_id:
            text = (
                f"Ваш код входа: <b>{code}</b>\n"
                f"Действует 5 минут. Никому его не сообщайте."
            )
            await send_telegram_message(chat_id=str(chat_id), text=text)

        return True, None

    async def verify_code(self, phone: str, code: str) -> Optional[Specialist]:
        normalized = _normalize_phone_ru(phone)
        specialist = await self.specialist_service.get_specialist_by_phone(normalized)
        if not specialist:
            return None

        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(LoginCode)
            .where(
                LoginCode.phone == normalized,
                LoginCode.specialist_id == specialist.id,
                LoginCode.used_at.is_(None)
            )
            .order_by(LoginCode.created_at.desc())
            .limit(1)
        )
        entry: Optional[LoginCode] = result.scalar_one_or_none()
        if not entry:
            return None

        # Проверки TTL и попыток
        if entry.expires_at <= now:
            # истек
            entry.used_at = now
            await self.db.commit()
            return None

        if entry.attempts >= MAX_VERIFY_ATTEMPTS:
            entry.used_at = now
            await self.db.commit()
            return None

        # Сверяем хеш
        if _hash_code(code) != entry.code_hash:
            entry.attempts += 1
            await self.db.commit()
            return None

        # Успех
        entry.used_at = now
        await self.db.commit()
        return specialist


