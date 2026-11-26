# Issue #126 — Télémétrie native FastAPI désactivée (Claude)
"""Les en-têtes de traçage (`traceparent`, `tracestate`) ne doivent jamais être analysés par l'API.

FastAPI ≥ 0.142 appelle `opentelemetry.propagate.extract` sur chaque requête dès qu'un fournisseur
de traces est configuré (SDK installé, `FASTAPI_OTEL_AUTO_CONFIGURE=true`, instrumentation
automatique…). Cette analyse est vulnérable (GHSA-mf5v-w3w3-f6cg, corrigée en 1.45.2 ;
GHSA-xcq7-p3pf-p88h, sans correctif). Le témoin prouve que le test détecte bien l'appel :
s'il échoue, FastAPI a changé de comportement et ce test doit être revu.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("fastapi.telemetry", reason="FastAPI < 0.142 : pas de télémétrie native")

from opentelemetry import propagate, trace  # noqa: E402

from app.main import app  # noqa: E402

TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


class _FournisseurConfigure(trace.TracerProvider):
    """Fournisseur de traces « configuré » : ni mandataire en attente, ni NoOp reconnu par FastAPI."""

    def get_tracer(self, *args, **kwargs):
        return trace.NoOpTracer()


@pytest.fixture
def appels_extract(monkeypatch):
    """Simule un fournisseur de traces configuré et compte les appels à `propagate.extract`."""
    appels = []
    extract_reel = propagate.extract

    def espion(*args, **kwargs):
        appels.append(args)
        return extract_reel(*args, **kwargs)

    fournisseur = _FournisseurConfigure()
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: fournisseur)
    monkeypatch.setattr(propagate, "extract", espion)
    return appels


def test_temoin_fastapi_par_defaut_analyse_traceparent(appels_extract):
    temoin = FastAPI()

    @temoin.get("/ping")
    def ping():
        return {"ok": True}

    r = TestClient(temoin).get("/ping", headers={"traceparent": TRACEPARENT})
    assert r.status_code == 200
    assert appels_extract, "le témoin doit montrer l'analyse de traceparent par FastAPI par défaut"


def test_api_n_analyse_pas_traceparent_meme_avec_fournisseur_configure(appels_extract):
    r = TestClient(app).get("/health", headers={"traceparent": TRACEPARENT, "tracestate": "a=1," * 2000})
    assert r.status_code == 200
    assert len(appels_extract) == 0, "traceparent analysé par l'API"


def test_traceparent_geant_sans_effet(appels_extract):
    r = TestClient(app).get("/health", headers={"traceparent": "00-" + "a" * 100_000})
    assert r.status_code == 200
    assert len(appels_extract) == 0, "traceparent analysé par l'API"
