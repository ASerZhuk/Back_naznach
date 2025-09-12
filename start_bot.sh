#!/bin/bash

echo "🤖 Запуск Telegram Bot для Naznach..."

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.11+"
    exit 1
fi

# Проверка версии Python
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Требуется Python $required_version или выше. Текущая версия: $python_version"
    exit 1
fi

# Создание виртуального окружения если его нет
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активация виртуального окружения
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Установка зависимостей
echo "📥 Установка зависимостей..."
pip install -r requirements.txt

# Не обновляем aiohttp, чтобы не ломать совместимость с aiogram 3.2.0

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Создайте его на основе env.example"
    echo "📝 Пример содержимого .env:"
    echo "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/naznach"
    echo "TELEGRAM_BOT_TOKEN=7944780464:AAEQX3ubMI1O-vPqzPcG6Nj_kHH3s0kTZBs"
    echo "SECRET_KEY=naznach_secret_key_2024"
    exit 1
fi

# Запуск бота
echo "🌟 Запуск Telegram Bot..."
echo "🤖 Бот будет отвечать на команды в Telegram"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

python bot.py
