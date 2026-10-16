from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", status_code=200, summary="Verificación de estado del servicio")
async def health_check():
    """
    Comprueba que el backend esté operativo y devuelve metadatos básicos.
    """
    return {
        "status": "healthy",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
