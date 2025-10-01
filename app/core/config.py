from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str
    
    # Telegram Bot
    telegram_bot_token: str
    telegram_bot_username: str = "app_naznach_bot"
    
    # App Settings
    debug: bool = False
    secret_key: str
    
    # Web App URL
    webapp_url: str = "https://2r29nsdq-3000.euw.devtunnels.ms/"
    
    # Backend API URL
    api_url: str = "https://sched-back.ru.tuna.am"

    # Telegram Webhook
    telegram_webhook_url: str = "https://sched-back.ru.tuna.am/api/telegram/webhook"
    telegram_webhook_secret: str = "naznach_webhook_secret_4b4e0df5a5d84b9e9a4b0c2e7b5f1a6c"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
