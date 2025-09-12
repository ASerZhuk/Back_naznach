#!/usr/bin/env python3
"""
Запуск FastAPI приложения
"""

import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Автоперезагрузка при изменении кода
        log_level="info"
    )
