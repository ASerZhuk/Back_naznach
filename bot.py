import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from app.core.config import settings
import aiohttp

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=settings.telegram_bot_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Глобальная сессия aiohttp для переиспользования
http_session = None

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
        specialist_user_id = None
        if len(command_args) > 1:
            specialist_user_id = command_args[1]
        
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
