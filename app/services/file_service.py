import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException
from PIL import Image
import io
from typing import Optional
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)

class FileService:
    """Сервис для работы с файлами"""
    
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    UPLOAD_DIR = "static/uploads"
    
    @classmethod
    def _ensure_upload_dir(cls):
        """Создает папку для загрузок если её нет"""
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)
    
    @classmethod
    def _is_valid_extension(cls, filename: str) -> bool:
        """Проверяет допустимое расширение файла"""
        return any(filename.lower().endswith(ext) for ext in cls.ALLOWED_EXTENSIONS)
    
    @classmethod
    def _is_valid_image(cls, file_content: bytes) -> bool:
        """Проверяет, что файл является валидным изображением"""
        try:
            Image.open(io.BytesIO(file_content))
            return True
        except Exception:
            return False
    
    @classmethod
    async def save_image(cls, file: UploadFile, specialist_id: str) -> str:
        """Сохраняет изображение и возвращает полный URL к файлу"""
        try:
            # Проверяем размер файла
            file_content = await file.read()
            if len(file_content) > cls.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Размер файла превышает {cls.MAX_FILE_SIZE // (1024*1024)}MB"
                )
            
            # Проверяем расширение
            if not cls._is_valid_extension(file.filename):
                raise HTTPException(
                    status_code=400,
                    detail=f"Недопустимый формат файла. Разрешены: {', '.join(cls.ALLOWED_EXTENSIONS)}"
                )
            
            # Проверяем, что это валидное изображение
            if not cls._is_valid_image(file_content):
                raise HTTPException(
                    status_code=400,
                    detail="Файл не является валидным изображением"
                )
            
            # Создаем папку если её нет
            cls._ensure_upload_dir()
            
            # Генерируем уникальное имя файла
            file_extension = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"specialist_{specialist_id}_{uuid.uuid4().hex}{file_extension}"
            file_path = os.path.join(cls.UPLOAD_DIR, unique_filename)
            
            # Сохраняем файл
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            logger.info(f"Изображение сохранено: {file_path}")
            
            # Возвращаем полный URL к файлу
            backend_url = settings.api_url.rstrip('/')
            return f"{backend_url}/static/uploads/{unique_filename}"
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка при сохранении изображения: {e}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка при сохранении изображения"
            )
    
    @classmethod
    async def delete_image(cls, image_path: str) -> bool:
        """Удаляет изображение по пути"""
        try:
            # Извлекаем имя файла из полного URL
            if image_path and "/static/uploads/" in image_path:
                filename = image_path.split("/static/uploads/")[-1]
                file_path = os.path.join(cls.UPLOAD_DIR, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Изображение удалено: {file_path}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при удалении изображения {image_path}: {e}")
            return False
    
    @classmethod
    def get_image_url(cls, filename: str) -> str:
        """Возвращает полный URL для изображения"""
        backend_url = settings.api_url.rstrip('/')
        return f"{backend_url}/static/uploads/{filename}"
