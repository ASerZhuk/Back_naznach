import json
import logging
from decimal import Decimal
from typing import Dict, Optional

import aiohttp
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..services import SpecialistService
from ..services.telegram_bot import telegram_bot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])

pending_payments: Dict[str, dict] = {}


def format_price(price_kopecks: Optional[int]) -> str:
    if price_kopecks is None:
        return "-"
    rubles = Decimal(price_kopecks) / Decimal(100)
    return f"{rubles:.2f} ₽"


def get_create_payment_url() -> str:
    base_url = settings.webapp_url.rstrip("/")
    return f"{base_url}/api/subscriptions/create-payment"


def build_payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить картой",
                    callback_data="payment:bank_card",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 Оплатить через СБП",
                    callback_data="payment:sbp",
                )
            ],
        ]
    )


async def request_payment_link(payload: dict, method: str) -> dict:
    plan = payload.get("plan", {})
    price_kopecks = plan.get("price_kopecks")

    amount_decimal = None
    if price_kopecks is not None:
        amount_decimal = Decimal(price_kopecks) / Decimal(100)
    elif plan.get("amount") is not None:
        amount_decimal = Decimal(str(plan["amount"]))

    if amount_decimal is None:
        raise ValueError("Не удалось определить сумму платежа")

    request_json = {
        "amount": f"{amount_decimal:.2f}",
        "currency": plan.get("currency", "RUB"),
        "description": plan.get("name") or "Оплата подписки",
        "specialistId": payload.get("specialist_id"),
        "planType": plan.get("plan_type"),
        "planName": plan.get("name"),
        "priceKopecks": price_kopecks,
        "paymentMethod": method,
        "telegramId": payload.get("telegram_id"),
    }

    url = get_create_payment_url()
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_json) as response:
            data = await response.json()
            if response.status >= 400:
                raise ValueError(
                    data
                    if isinstance(data, str)
                    else data.get("error", "Не удалось создать платеж")
                )
            return data


async def process_payment_command(chat_id: str, user_id: str, payload: dict):
    payload["telegram_id"] = user_id
    pending_payments[user_id] = payload

    plan = payload.get("plan", {})
    plan_name = plan.get("name", "подписка")
    price_text = format_price(plan.get("price_kopecks"))

    text_lines = [
        "Вы собираетесь оформить подписку.",
        f"\n<b>Тариф:</b> {plan_name}",
        f"<b>Стоимость:</b> {price_text}",
        "\nВыберите способ оплаты:",
    ]

    await telegram_bot.bot.send_message(
        chat_id=chat_id,
        text="\n".join(text_lines),
        parse_mode="HTML",
        reply_markup=build_payment_keyboard(),
        disable_web_page_preview=True,
    )
    logger.info("Пользователю %s отправлено меню выбора способа оплаты (webhook)", user_id)


async def process_payment_callback(callback_query: dict) -> bool:
    data = callback_query.get("data") or ""
    if not data.startswith("payment:"):
        return False

    _, method = data.split(":", maxsplit=1)
    callback_id = callback_query.get("id")
    from_user = callback_query.get("from") or {}
    user_id = str(from_user.get("id"))
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id")) if chat.get("id") is not None else None
    message_id = message.get("message_id")

    payload = pending_payments.get(user_id)

    if not payload:
        await telegram_bot.bot.answer_callback_query(
            callback_id,
            text="Данные устарели. Откройте мини-приложение ещё раз.",
            show_alert=True,
        )
        if chat_id:
            await telegram_bot.bot.send_message(
                chat_id=chat_id,
                text="Не найдено данных для оплаты. Попробуйте снова через мини-приложение.",
            )
        return True

    if method == "sbp":
        await telegram_bot.bot.answer_callback_query(
            callback_id,
            text="Оплата через СБП скоро будет доступна",
            show_alert=True,
        )
        if chat_id:
            await telegram_bot.bot.send_message(
                chat_id=chat_id,
                text="Оплата через СБП пока в разработке. Пожалуйста, выберите оплату картой.",
            )
        return True

    if method != "bank_card":
        await telegram_bot.bot.answer_callback_query(
            callback_id,
            text="Неизвестный способ оплаты",
            show_alert=True,
        )
        return True

    await telegram_bot.bot.answer_callback_query(callback_id)

    try:
        payment_response = await request_payment_link(payload, method)
    except ValueError as error:
        logger.error("Не удалось создать платеж (webhook): %s", error)
        if chat_id:
            await telegram_bot.bot.send_message(
                chat_id=chat_id,
                text=f"Не удалось создать платеж: {error}",
            )
        return True
    except Exception as error:
        logger.exception("Непредвиденная ошибка при создании платежа (webhook)")
        if chat_id:
            await telegram_bot.bot.send_message(
                chat_id=chat_id,
                text="Произошла ошибка при создании платежа. Попробуйте позже.",
            )
        return True

    confirmation_url = payment_response.get("confirmationUrl")
    payment_id = payment_response.get("paymentId")

    if not confirmation_url:
        logger.error("В ответе отсутствует confirmationUrl (webhook): %s", payment_response)
        if chat_id:
            await telegram_bot.bot.send_message(
                chat_id=chat_id,
                text="Не удалось получить ссылку на оплату. Попробуйте позже.",
            )
        return True

    pending_payments.pop(user_id, None)

    if chat_id and message_id:
        try:
            await telegram_bot.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None,
            )
        except Exception:
            pass

    button_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Перейти к оплате",
                    url=confirmation_url,
                )
            ]
        ]
    )

    plan = payload.get("plan", {})
    plan_name = plan.get("name", "подписка")
    price_text = format_price(plan.get("price_kopecks"))
    header = f"Счёт #{payment_id} создан." if payment_id else "Счёт создан."

    message_lines = [
        header,
        f"<b>Тариф:</b> {plan_name}",
        f"<b>Стоимость:</b> {price_text}",
        "\nНажмите кнопку ниже, чтобы перейти на страницу оплаты ЮKassa. После успешного платежа мы начислим подписку и пришлём уведомление.",
    ]

    if chat_id:
        await telegram_bot.bot.send_message(
            chat_id=chat_id,
            text="\n".join(message_lines),
            parse_mode="HTML",
            reply_markup=button_keyboard,
            disable_web_page_preview=True,
        )
    logger.info("Платёж %s создан для пользователя %s (webhook)", payment_id, user_id)

    return True


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Вебхук для Telegram. Обрабатывает команды, данные из mini app и ответы на кнопки."""
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    data = await request.json()
    print("[webhook] update:", data)

    callback_query = data.get("callback_query")
    if callback_query:
        handled = await process_payment_callback(callback_query)
        if handled:
            return {"ok": True}

    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    web_app_data = message.get("web_app_data")
    if web_app_data:
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id")) if chat.get("id") is not None else None
        from_user = message.get("from") or {}
        user_id = str(from_user.get("id"))

        try:
            payload = json.loads(web_app_data.get("data", "{}"))
        except Exception as e:
            logger.error(f"Не удалось распарсить web_app_data: {e}")
            if chat_id:
                await telegram_bot.bot.send_message(
                    chat_id=chat_id,
                    text="Не удалось обработать данные из приложения. Попробуйте снова.",
                )
            return {"ok": True}

        if payload.get("command") == "payment" and chat_id:
            await process_payment_command(chat_id, user_id, payload)
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
                async with session.post(
                    f"{settings.api_url}/api/auth/register",
                    json={
                        "telegram_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                    },
                ) as response:
                    # Проверяем статус ответа для логирования
                    if response.status not in [200, 201]:
                        logger.warning(f"Неожиданный статус при регистрации пользователя {user_id}: {response.status}")

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
