#!/bin/bash

echo "🚀 Запуск Naznach Backend API..."

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

# Создание базы данных
echo "🗄️  Создание базы данных..."
python create_db.py

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Создайте его на основе env.example"
    echo "📝 Пример содержимого .env:"
    echo "DATABASE_URL=postgresql://username:password@localhost:5432/database_name"
    echo "TELEGRAM_BOT_TOKEN=your_bot_token_here"
    echo "SECRET_KEY=your_secret_key_here"
    exit 1
fi

# Запуск приложения
echo "🌟 Запуск FastAPI приложения..."
echo "📖 API документация будет доступна по адресу: http://localhost:8000/docs"
echo "🔍 Health check: http://localhost:8000/health"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

python run.py
