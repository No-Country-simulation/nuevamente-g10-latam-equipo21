from fastapi import APIRouter
from app.api.v1.endpoints import documents, health

api_router = APIRouter()

# Registro modular de routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(documents.router, tags=["Documents"])
