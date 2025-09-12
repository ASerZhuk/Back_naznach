from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from .api import appointments, services, users, specialists, auth, grafik, telegram, specialist_auth
from .api.subscriptions import router as subscriptions_router
from .api.specialist_pages import router as specialist_pages
from .core.database import engine, Base
import asyncio
import os
from .services.telegram_bot import telegram_bot
from .core.config import settings
from .core.database import AsyncSessionLocal
from sqlalchemy import select, and_
from .models.appointments import Appointments
from .services.telegram_bot import send_telegram_notification
from datetime import datetime, timedelta


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Создание FastAPI приложения
app = FastAPI(
    title="Naznach Backend API",
    description="Backend API для приложения записи к специалистам",
    version="1.0.0"
)

# Создание таблиц при запуске
@app.on_event("startup")
async def startup_event():
    await create_tables()
    
    # Создаем папку для статических файлов если её нет
    os.makedirs("static/uploads", exist_ok=True)

    # Устанавливаем webhook для Telegram
    try:
        await telegram_bot.bot.set_webhook(
            url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret
        )
    except Exception as e:
        print(f"Не удалось установить webhook: {e}")

    # Запускаем фоновую задачу напоминаний (ежесуточно, за день до события)
    async def reminders_worker():
        while True:
            try:
                now = datetime.now()
                # Время следующего запуска — завтра в 09:00 локального времени
                next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if now >= next_run:
                    next_run = next_run + timedelta(days=1)
                sleep_seconds = (next_run - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

                # Дата для напоминаний — завтра
                target_date = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select, and_
                    result = await session.execute(
                        select(Appointments).where(
                            and_(
                                Appointments.date == target_date,
                                Appointments.status == 'active',
                                (Appointments.reminder_sent == False) | (Appointments.reminder_sent.is_(None))
                            )
                        )
                    )
                    appointments = result.scalars().all()

                    for appt in appointments:
                        price = (appt.service_price or '').strip()
                        valuta = (appt.service_valuta or '').strip()
                        price_line = f" {price} {valuta}".strip() if price or valuta else ''

                        message = (
                            f"<b>🔔 Напоминание о записи на завтра</b>\n\n"
                            f"🗓️ <b>Дата:</b> {target_date}\n"
                            f"⏰ <b>Время:</b> {appt.time}\n"
                            f"💇 <b>Услуга:</b> {appt.service_name or '-'}{price_line}\n"
                            f"👤 <b>Специалист:</b> {appt.specialist_name or ''} {appt.specialist_last_name or ''}\n"
                            f"📍 <b>Адрес:</b> {appt.specialist_address or '-'}\n"
                            f"📞 <b>Телефон:</b> {appt.specialist_phone or '-'}"
                        )

                        await send_telegram_notification(message, appt.client_id)
                        appt.reminder_sent = True
                        appt.reminder_sent_at = datetime.utcnow()

                    if appointments:
                        await session.commit()
            except Exception as e:
                # Логируем и пробуем через минуту, чтобы не падать навсегда
                print(f"Ошибка в reminders_worker: {e}")
                await asyncio.sleep(60)

    asyncio.create_task(reminders_worker())

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.include_router(auth, prefix="/api")
app.include_router(appointments, prefix="/api")
app.include_router(services, prefix="/api")
app.include_router(users, prefix="/api")
app.include_router(specialists, prefix="/api")
app.include_router(grafik, prefix="/api")
app.include_router(telegram, prefix="/api")
app.include_router(specialist_auth, prefix="/api")
app.include_router(subscriptions_router, prefix="/api")
app.include_router(specialist_pages)


@app.get("/")
async def root():
    """Корневой endpoint"""
    return RedirectResponse(url="/login")
    # return {
    #     "message": "Naznach Backend API",
    #     "version": "1.0.0",
    #     "status": "running"
    # }


@app.get("/health")
async def health_check():
    """Проверка состояния API"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
