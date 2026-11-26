import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import accueil, admin, admin_contenu, archivage, cartes, classes_pilotes, collaboration, cours, redactions, diagnostic, domaines, eleves, enseignants, enseignants_contenu, health, parents, ressources, anglais, anglais_eleves, enfants, familles, francais, francais_eleves, masse, pkp_math, prevalidation_ia, repertoire, remarques, simulation, suivi, validation_maths

# En production, la documentation interactive n'est pas exposée publiquement.
app = FastAPI(
    title="PKP Éducation",
    version="1.0.0",
    docs_url=None if settings.production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.production else "/openapi.json",
    # Issue #126 : télémétrie OpenTelemetry native de FastAPI (≥ 0.142) coupée, le projet ne l'utilise pas.
    # Sinon, dès qu'un fournisseur de traces est configuré, chaque requête analyse `traceparent` et
    # `tracestate` (GHSA-mf5v-w3w3-f6cg, GHSA-xcq7-p3pf-p88h). Les versions antérieures ignorent ce réglage.
    telemetry={"tracing": False, "metrics": False, "logs": False},
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
app.include_router(diagnostic.router)  # issue #162 : /eleves/moi/diagnostic, /enseignants/classes/{id}/diagnostic
app.include_router(redactions.router)  # issue #179 : /eleves/moi/redactions, /enseignants/.../redactions
app.include_router(simulation.router)  # issue #184 : vue élève simulée
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
app.include_router(classes_pilotes.router)  # issue #176
app.include_router(admin_contenu.router)
app.include_router(anglais_eleves.router)
app.include_router(anglais.router)
app.include_router(francais_eleves.router)  # issue #212 : /francais/eleve/*
app.include_router(francais.router)
app.include_router(enfants.router)
app.include_router(familles.router)
app.include_router(pkp_math.router)
app.include_router(remarques.router)
app.include_router(collaboration.router)  # issue #171 : /collaboration/*
app.include_router(accueil.router)  # issue #172 : /admin/accueil/* (« Accueil et demandes »)
app.include_router(prevalidation_ia.router_admin)
app.include_router(prevalidation_ia.router_service)
