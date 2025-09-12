import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_
from ..core.database import AsyncSessionLocal
from ..models.appointments import Appointments
from ..services.telegram_bot import send_telegram_notification, telegram_bot


def format_date_ru(date_str: str) -> str:
    # date_str: dd.mm.yyyy
    try:
        d, m, y = map(int, date_str.split('.'))
        dt = datetime(y, m, d)
        return dt.strftime('%d.%m.%Y')
    except Exception:
        return date_str


async def send_reminders_for_date(target_date_str: str):
    async with AsyncSessionLocal() as session:
        # Найти активные записи на target_date_str без отправленного напоминания
        result = await session.execute(
            select(Appointments).where(
                and_(
                    Appointments.date == target_date_str,
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
                f"🗓️ <b>Дата:</b> {format_date_ru(appt.date)}\n"
                f"⏰ <b>Время:</b> {appt.time}\n"
                f"💇 <b>Услуга:</b> {appt.service_name or '-'}{price_line}\n"
                f"👤 <b>Специалист:</b> {appt.specialist_name or ''} {appt.specialist_last_name or ''}\n"
                f"📍 <b>Адрес:</b> {appt.specialist_address or '-'}\n"
                f"📞 <b>Телефон:</b> {appt.specialist_phone or '-'}"
            )

            # только клиенту
            await send_telegram_notification(message, appt.client_id)

            # пометить как отправленное
            appt.reminder_sent = True
            appt.reminder_sent_at = datetime.now(timezone.utc)

        if appointments:
            await session.commit()


async def main():
    # Рассчитать завтрашнюю дату в формате dd.mm.yyyy (локально)
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    target_date_str = tomorrow.strftime('%d.%m.%Y')
    await send_reminders_for_date(target_date_str)
    # Закрываем сессию Telegram при завершении скрипта
    try:
        await telegram_bot.close()
    except Exception:
        pass


if __name__ == '__main__':
    asyncio.run(main())


