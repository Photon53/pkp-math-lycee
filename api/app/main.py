from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import admin, admin_contenu, cours, eleves, enseignants, enseignants_contenu, health, ressources

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
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(eleves.router)
app.include_router(enseignants.router)
app.include_router(cours.router)
app.include_router(enseignants_contenu.router)
app.include_router(ressources.router)
app.include_router(admin.router)
app.include_router(admin_contenu.router)
