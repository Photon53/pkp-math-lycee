from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import cours, eleves, enseignants, health

# En production, la documentation interactive n'est pas exposée publiquement.
app = FastAPI(
    title="PKP Math Lycée",
    version="1.0.0",
    docs_url=None if settings.production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(eleves.router)
app.include_router(enseignants.router)
app.include_router(cours.router)
