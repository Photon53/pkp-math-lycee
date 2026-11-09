import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import admin, admin_contenu, archivage, cartes, cours, domaines, eleves, enseignants, enseignants_contenu, health, parents, ressources, anglais, anglais_eleves, enfants, familles, masse, pkp_math, repertoire, remarques, suivi, validation_maths

# En production, la documentation interactive n'est pas exposée publiquement.
app = FastAPI(
    title="Boussole",
    version="1.0.0",
    docs_url=None if settings.production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.production else "/openapi.json",
)

if settings.production and settings.servir_questions_non_validees:
    logging.getLogger("uvicorn.error").warning(
        "PKP_SERVIR_QUESTIONS_NON_VALIDEES=true : les compétences sans question validée servent des questions non relues."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(domaines.router)
app.include_router(suivi.router)  # avant eleves et enseignants : chemins plus précis
app.include_router(eleves.router)
app.include_router(enseignants.router)
app.include_router(parents.router)
app.include_router(cours.router)
app.include_router(enseignants_contenu.router)
app.include_router(validation_maths.router)
app.include_router(ressources.router)
app.include_router(masse.router)
app.include_router(cartes.router)
app.include_router(repertoire.router)
app.include_router(archivage.router)
app.include_router(admin.router)
app.include_router(admin_contenu.router)
app.include_router(anglais_eleves.router)
app.include_router(anglais.router)
app.include_router(enfants.router)
app.include_router(familles.router)
app.include_router(pkp_math.router)
app.include_router(remarques.router)
