from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from .deps import require_specialist

router = APIRouter(prefix="", tags=["specialist-pages"]) 
templates = Jinja2Templates(directory="templates")


@router.get("/login")
async def login_page(request: Request):
    from ..core.config import settings
    return templates.TemplateResponse("specialist_login.html", {"request": request, "bot_username": settings.telegram_bot_username})


@router.get("/login/code")
async def code_page(request: Request):
    return templates.TemplateResponse("specialist_code.html", {"request": request})


@router.get("/dashboard")
async def cabinet_page(request: Request, specialist = Depends(require_specialist)):
    return templates.TemplateResponse("dashboard/layout.html", {"request": request, "specialist": specialist})


