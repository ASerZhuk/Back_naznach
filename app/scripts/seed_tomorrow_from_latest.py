import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, desc
from ..core.database import AsyncSessionLocal
from ..models.appointments import Appointments


async def main():
    async with AsyncSessionLocal() as session:
        # Берём последнюю запись как шаблон
        result = await session.execute(select(Appointments).order_by(desc(Appointments.id)).limit(1))
        last = result.scalar_one_or_none()
        if not last:
            print("Нет существующих записей для копирования. Создайте хотя бы одну запись вручную.")
            return

        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')

        new_appt = Appointments(
            client_id=last.client_id,
            first_name=last.first_name,
            last_name=last.last_name,
            specialist_id=last.specialist_id,
            service_id=last.service_id,
            service_name=last.service_name,
            service_valuta=last.service_valuta,
            date=tomorrow,
            time=last.time or '10:00',
            phone=last.phone,
            specialist_name=last.specialist_name,
            specialist_last_name=last.specialist_last_name,
            specialist_address=last.specialist_address,
            service_price=last.service_price,
            specialist_phone=last.specialist_phone,
            status='active',
            reminder_sent=False,
        )

        session.add(new_appt)
        await session.commit()
        await session.refresh(new_appt)
        print(f"Создана тестовая запись на завтра: id={new_appt.id} {new_appt.date} {new_appt.time}")


if __name__ == '__main__':
    asyncio.run(main())


