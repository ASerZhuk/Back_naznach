from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from ..core.config import settings
import asyncio
from typing import Optional
from aiogram.client.session.aiohttp import AiohttpSession


class TelegramBotService:
    def __init__(self):
        # Общая сессия для работы и вебхуков
        self.bot = Bot(token=settings.telegram_bot_token, session=AiohttpSession())
    
    async def send_message(self, chat_id: str, text: str, parse_mode: Optional[str] = "HTML", reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """Отправить сообщение пользователю"""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")
            return False
    
    async def send_notification(self, chat_id: str, message: str, parse_mode: Optional[str] = "HTML", reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """Отправить уведомление пользователю"""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"🔔 <b>Уведомление</b>\n\n{message}",
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")
            return False
    
    async def close(self):
        """Закрыть соединение с ботом"""
        await self.bot.session.close()


# Глобальный экземпляр бота
telegram_bot = TelegramBotService()


async def send_telegram_notification(message: str, chat_id: Optional[str] = None, parse_mode: Optional[str] = "HTML", reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    """Функция для отправки уведомлений в Telegram"""
    if not chat_id:
        return False
    
    return await telegram_bot.send_notification(chat_id, message, parse_mode=parse_mode, reply_markup=reply_markup)


async def send_telegram_message(chat_id: str, text: str, parse_mode: Optional[str] = "HTML", reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    """Функция для отправки сообщений в Telegram"""
    return await telegram_bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
