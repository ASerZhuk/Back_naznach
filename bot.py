import asyncio
import base64
import json
import logging
from decimal import Decimal
from typing import Dict, Optional

import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=settings.telegram_bot_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Глобальная сессия aiohttp для переиспользования
http_session = None
pending_payments: Dict[str, dict] = {}
plan_cache: Dict[str, dict] = {}


def format_price(price_kopecks: Optional[int]) -> str:
    if price_kopecks is None:
        return "-"
    try:
        value = int(price_kopecks)
    except (TypeError, ValueError):
        return "-"
    rubles = Decimal(value) / Decimal(100)
    return f"{rubles:.2f} ₽"


def get_create_payment_url() -> str:
    base_url = settings.webapp_url.rstrip("/")
    return f"{base_url}/api/subscriptions/create-payment"


def build_payment_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="💳 Оплатить картой",
                    callback_data="payment:bank_card",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📱 Оплатить через СБП",
                    callback_data="payment:sbp",
                )
            ],
        ]
    )


async def request_payment_link(payload: dict, method: str) -> dict:
    session = await get_http_session()
    plan = payload.get("plan", {})
    price_kopecks = plan.get("price_kopecks")

    amount_decimal = None
    if price_kopecks is not None:
        amount_decimal = Decimal(str(price_kopecks)) / Decimal(100)
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
    async with session.post(url, json=request_json) as response:
        data = await response.json()
        if response.status >= 400:
            raise ValueError(data if isinstance(data, str) else data.get("error", "Не удалось создать платеж"))
        return data


def decode_payment_start_param(raw_param: str) -> Optional[dict]:
    if not raw_param:
        return None
    padding = "=" * (-len(raw_param) % 4)
    try:
        decoded = base64.urlsafe_b64decode((raw_param + padding).encode("utf-8")).decode("utf-8")
    except Exception:
        return None

    parts = decoded.split("|")
    if len(parts) < 6 or parts[0] != "payment":
        return None

    specialist_id = parts[2] or None
    plan_type = parts[3] or None
    price_raw = parts[4] or None
    currency = parts[5] or "RUB"

    if not specialist_id or not plan_type:
        return None

    try:
        price_kopecks = int(price_raw) if price_raw else None
    except (TypeError, ValueError):
        price_kopecks = None

    return {
        "specialist_id": specialist_id,
        "plan_type": plan_type,
        "price_kopecks": price_kopecks,
        "currency": currency,
    }


async def get_plan_details(plan_type: Optional[str]) -> Optional[dict]:
    if not plan_type:
        return None

    cached = plan_cache.get(plan_type)
    if cached:
        return cached

    session = await get_http_session()
    try:
        async with session.get(f"{settings.api_url}/api/subscriptions/plans") as response:
            if response.status != 200:
                return None
            plans = await response.json()
            for plan in plans:
                plan_type_value = plan.get("plan_type")
                if plan_type_value:
                    plan_cache[plan_type_value] = plan
            return plan_cache.get(plan_type)
    except Exception as exc:
        logger.error("Не удалось получить список планов: %s", exc)
        return None


async def process_payment_command(chat_id: str, user_id: str, payload: dict):
    if not user_id:
        await bot.send_message(chat_id, "Не удалось определить пользователя. Попробуйте снова.")
        return

    payload = dict(payload)
    payload["telegram_id"] = user_id

    specialist_id = payload.get("specialist_id")
    plan = payload.setdefault("plan", {})
    plan_type = plan.get("plan_type")

    if not specialist_id or not plan_type:
        await bot.send_message(chat_id, "Не удалось определить данные для оплаты. Попробуйте снова.")
        return

    plan_details = await get_plan_details(plan_type)
    if plan_details:
        plan.setdefault("name", plan_details.get("name"))
        plan.setdefault("price_kopecks", plan.get("price_kopecks") or plan_details.get("price"))
        plan.setdefault("currency", plan.get("currency") or "RUB")
        plan.setdefault("duration_days", plan.get("duration_days") or plan_details.get("duration_days"))

    pending_payments[user_id] = payload

    plan_name = plan.get("name") or plan_type
    price_text = format_price(plan.get("price_kopecks"))

    text_lines = [
        "Вы собираетесь оформить подписку.",
        f"\n<b>Тариф:</b> {plan_name}",
        f"<b>Стоимость:</b> {price_text}",
        "\nВыберите способ оплаты:",
    ]

    await bot.send_message(
        chat_id=chat_id,
        text="\n".join(text_lines),
        parse_mode="HTML",
        reply_markup=build_payment_keyboard(),
        disable_web_page_preview=True,
    )
    logger.info("Пользователю %s отправлено меню выбора способа оплаты", user_id)

async def get_http_session():
    """Получить глобальную HTTP сессию"""
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

async def close_http_session():
    """Закрыть глобальную HTTP сессию"""
    global http_session
    if http_session and not http_session.closed:
        await http_session.close()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    try:
        user_id = str(message.from_user.id)
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        # Получаем параметр команды (user_id специалиста)
        command_args = message.text.split() if message.text else []
        start_param = command_args[1] if len(command_args) > 1 else None

        decoded_payment = decode_payment_start_param(start_param or "") if start_param else None
        if decoded_payment:
            payload = {
                "specialist_id": decoded_payment.get("specialist_id"),
                "plan": {
                    "plan_type": decoded_payment.get("plan_type"),
                    "price_kopecks": decoded_payment.get("price_kopecks"),
                    "currency": decoded_payment.get("currency"),
                },
            }
            await process_payment_command(str(message.chat.id), user_id, payload)
            return

        specialist_user_id = start_param

        # Если есть параметр специалиста, показываем информацию о специалисте
        if specialist_user_id:
            await show_specialist_info(message, specialist_user_id)
            return
        
        # Обычная логика для /start без параметров
        # Проверяем, зарегистрирован ли пользователь
        session = await get_http_session()
        try:
            async with session.get(f"{settings.api_url}/api/auth/user/{user_id}") as response:
                if response.status == 200:
                    # Пользователь уже зарегистрирован
                    user_data = await response.json()
                    logger.info(f"Пользователь {user_id} уже зарегистрирован")
                    
                    # Показываем кнопку Mini App
                    await show_mini_app_button(message)
                else:
                    # Пользователь не зарегистрирован - регистрируем
                    logger.info(f"Регистрируем нового пользователя {user_id}")
                    await register_new_user(message, user_id, username, first_name, last_name)
        except Exception as e:
            logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
            await message.answer("Произошла ошибка. Попробуйте позже.")
                    
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")


@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    """Получаем данные из мини-приложения и предлагаем выбрать способ оплаты."""
    try:
        raw_data = message.web_app_data.data
        payload = json.loads(raw_data)
    except Exception as e:
        logger.error(f"Не удалось распарсить web_app_data: {e}")
        await message.answer("Не удалось обработать данные из приложения. Попробуйте снова.")
        return

    if payload.get("command") != "payment":
        logger.info("Получена web_app_data с неизвестной командой: %s", payload.get("command"))
        return

    user_id = str(message.from_user.id)
    await process_payment_command(str(message.chat.id), user_id, payload)


@dp.callback_query(F.data.startswith("payment:"))
async def handle_payment_choice(callback: types.CallbackQuery):
    data = callback.data or ""
    _, method = data.split(":", maxsplit=1)
    user_id = str(callback.from_user.id)

    payload = pending_payments.get(user_id)
    if not payload:
        await callback.answer("Данные устарели. Откройте мини-приложение ещё раз.", show_alert=True)
        await callback.message.answer("Не найдено данных для оплаты. Попробуйте снова через мини-приложение.")
        return

    if method == "sbp":
        await callback.answer("Скоро будет доступно", show_alert=True)
        await callback.message.answer(
            "Оплата через СБП находится в разработке. Пожалуйста, выберите оплату картой."
        )
        return

    if method != "bank_card":
        await callback.answer("Неизвестный способ оплаты", show_alert=True)
        return

    try:
        await callback.answer("Формируем ссылку...")
    except Exception:
        logger.debug("Не удалось отправить callback.answer", exc_info=True)

    try:
        payment_response = await request_payment_link(payload, method)
    except ValueError as error:
        logger.error("Не удалось создать платеж: %s", error)
        await callback.message.answer(f"Не удалось создать платеж: {error}")
        return
    except Exception as error:
        logger.exception("Непредвиденная ошибка при создании платежа")
        await callback.message.answer("Произошла ошибка при создании платежа. Попробуйте позже.")
        return

    confirmation_url = payment_response.get("confirmationUrl")
    payment_id = payment_response.get("paymentId")

    if not confirmation_url:
        logger.error("В ответе отсутствует confirmationUrl: %s", payment_response)
        await callback.message.answer("Не удалось получить ссылку на оплату. Попробуйте позже.")
        return

    pending_payments.pop(user_id, None)

    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass

    button_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
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
        "\nНажмите кнопку ниже, чтобы перейти на страницу оплаты ЮKassa. После успешного платежа мы начислим подписку и пришлём уведомление." 
    ]

    await callback.message.answer(
        "\n".join(message_lines),
        parse_mode="HTML",
        reply_markup=button_keyboard,
        disable_web_page_preview=True,
    )
    logger.info("Платёж %s создан для пользователя %s", payment_id, user_id)

async def register_new_user(message: types.Message, user_id: str, username: str, first_name: str, last_name: str):
    """Регистрация нового пользователя"""
    try:
        # Регистрируем пользователя через API
        session = await get_http_session()
        user_data = {
            "telegram_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name
        }
        
        async with session.post(f"{settings.api_url}/api/auth/register", json=user_data) as response:
            if response.status == 200:
                logger.info(f"Пользователь {user_id} успешно зарегистрирован")
                # Показываем кнопку Mini App
                await show_mini_app_button(message)
            else:
                logger.error(f"Ошибка при регистрации пользователя {user_id}")
                await message.answer("Ошибка при регистрации. Попробуйте позже.")
                    
    except Exception as e:
        logger.error(f"Ошибка при регистрации пользователя {user_id}: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

async def show_specialist_info(message: types.Message, specialist_user_id: str):
    """Показать информацию о специалисте и кнопку для записи"""
    try:
        # Получаем информацию о специалисте через API
        session = await get_http_session()
        async with session.get(f"{settings.api_url}/api/specialists/{specialist_user_id}") as response:
            if response.status == 200:
                specialist_data = await response.json()
                
                # Формируем сообщение о специалисте
                specialist_text = f"👨‍⚕️ **{specialist_data.get('first_name', '')} {specialist_data.get('last_name', '')}**\n\n"
                
                if specialist_data.get('phone'):
                    specialist_text += f"📞 Телефон: {specialist_data['phone']}\n"
                
                if specialist_data.get('description'):
                    specialist_text += f"📝 Описание: {specialist_data['description']}\n"
                
                specialist_text += "\n💼 Записаться на прием можно через приложение:"
                
                # Создаем кнопку для перехода к специалисту в mini app
                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="📅 Записаться на прием",
                                web_app=types.WebAppInfo(url=f"{settings.webapp_url}/specialist_view/{specialist_user_id}")
                            )
                        ]
                    ]
                )
                
                await message.answer(specialist_text, reply_markup=keyboard, parse_mode="Markdown")
                logger.info(f"Показана информация о специалисте {specialist_user_id}")
                
            else:
                await message.answer("❌ Специалист не найден. Проверьте ссылку.")
                logger.warning(f"Специалист {specialist_user_id} не найден")
                
    except Exception as e:
        logger.error(f"Ошибка при получении информации о специалисте {specialist_user_id}: {e}")
        await message.answer("Произошла ошибка при загрузке информации о специалисте. Попробуйте позже.")

async def show_mini_app_button(message: types.Message):
    """Показать кнопку для перехода в Mini App"""
    try:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🚀 Открыть приложение",
                        web_app=types.WebAppInfo(url=settings.webapp_url)
                    )
                ]
            ]
        )
        
        await message.answer(
            "Добро пожаловать в приложение «Назначь»! 🎉\n\n"
            "Нажмите кнопку ниже, чтобы открыть приложение и выбрать свою роль.",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при показе кнопки Mini App: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

async def main():
    """Главная функция"""
    logger.info("Запуск Telegram бота...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()
        await close_http_session()

if __name__ == "__main__":
    asyncio.run(main())
