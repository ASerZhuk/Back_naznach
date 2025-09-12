from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..core.config import settings
from ..services.telegram_bot import telegram_bot
from ..services import SpecialistService
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import aiohttp

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Вебхук для Telegram. Обрабатывает /start и /start <user_id>."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    data = await request.json()
    print("[webhook] update:", data)
    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat") or {}
    chat_id = str(chat.get("id"))
    text = message.get("text") or ""

    # /start
    if text.startswith("/start"):
        parts = text.split()
        # /start <user_id>
        if len(parts) > 1:
            specialist_user_id = parts[1]
            # Берем специалиста напрямую из БД и сохраняем chat_id при необходимости
            specialist_service = SpecialistService(db)
            specialist = await specialist_service.get_specialist_by_user_id(specialist_user_id)
            if specialist:
                if not specialist.chat_id:
                    specialist.chat_id = chat_id
                    await db.commit()

                first_name = specialist.first_name or ""
                last_name = specialist.last_name or ""
                phone = specialist.phone
                description = specialist.description

                lines = [f"👨‍⚕️ {first_name} {last_name}".strip()]
                if phone:
                    lines.append(f"\n📞 Телефон: {phone}")
                if description:
                    lines.append(f"\n📝 Описание: {description}")
                lines.append("\n💼 Записаться на прием можно через приложение:")
                text_msg = "\n".join(lines)

                # Кнопка с web_app
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📅 Записаться на прием",
                                web_app=WebAppInfo(url=f"{settings.webapp_url.rstrip('/')}/specialist_view/{specialist_user_id}")
                            )
                        ]
                    ]
                )
                await telegram_bot.bot.send_message(chat_id=chat_id, text=text_msg, reply_markup=kb, parse_mode="Markdown")
            else:
                await telegram_bot.bot.send_message(chat_id=chat_id, text="❌ Специалист не найден. Проверьте ссылку.")
        else:
            # /start без параметра: регистрация пользователя и кнопка открытия приложения
            user = message.get("from") or {}
            user_id = str(user.get("id"))
            username = user.get("username")
            first_name = user.get("first_name")
            last_name = user.get("last_name")

            # Регистрируем пользователя на бэке (идемпотентно)
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{settings.api_url}/api/auth/register",
                    json={
                        "telegram_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                    },
                )

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🚀 Открыть приложение",
                            web_app=WebAppInfo(url=settings.webapp_url)
                        )
                    ]
                ]
            )
            await telegram_bot.bot.send_message(
                chat_id=chat_id,
                text=(
                    "Добро пожаловать в приложение «Назначь»! 🎉\n\n"
                    "Нажмите кнопку ниже, чтобы открыть приложение и выбрать свою роль."
                ),
                reply_markup=kb,
            )

    return {"ok": True}

# Дублируем маршрут с завершающим слэшем на случай настроек прокси
@router.post("/webhook/")
async def telegram_webhook_slash(request: Request, db: AsyncSession = Depends(get_db)):
    return await telegram_webhook(request, db)


@router.post("/set-webhook")
async def set_webhook():
    try:
        await telegram_bot.bot.set_webhook(
            url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=False,
        )
        info = await telegram_bot.bot.get_webhook_info()
        return {"ok": True, "info": info.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-webhook")
async def delete_webhook():
    try:
        await telegram_bot.bot.delete_webhook(drop_pending_updates=False)
        info = await telegram_bot.bot.get_webhook_info()
        return {"ok": True, "info": info.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhook-info")
async def webhook_info():
    info = await telegram_bot.bot.get_webhook_info()
    return info.model_dump()


