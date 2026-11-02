"""Contrôles de génération des quatre cahiers PKP Anglais."""
import io
from pathlib import Path

import pypdf
import pytest
from pkp_anglais.contenu import charger_seance
from pkp_anglais.seances import generer_pack_animateur, generer_pack_eleve

from app.anglais_pdf import charger_ressources, produire_pdf, verifier_ressources

ROOT = Path(__file__).resolve().parents[2] / "contenu" / "anglais" / "seances"
CASES = [
    ("4e", "4e-01-pilote.json"), ("4e", "4e-02-pilote.json"),
    ("3e", "3e-01-pilote.json"), ("3e", "3e-02-pilote.json"),
]


def _lire(pdf: bytes) -> tuple[str, list[str]]:
    """Texte (espaces normalisés) et liens cliquables d'un PDF."""
    lecteur = pypdf.PdfReader(io.BytesIO(pdf))
    texte = " ".join(" ".join(page.extract_text().split()) for page in lecteur.pages)
    liens = [a.get_object()["/A"]["/URI"] for page in lecteur.pages for a in (page.get("/Annots") or [])
             if "/A" in a.get_object()]
    return texte, liens


@pytest.mark.parametrize("niveau,filename", CASES)
def test_cahiers_complets(niveau, filename):
    seance = charger_seance(ROOT / niveau / filename)
    for public, pack in [
        ("eleve", generer_pack_eleve(seance)),
        ("animateur", generer_pack_animateur(seance)),
    ]:
        pdf = produire_pdf(pack, public)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 3500
        if public == "eleve":
            # Cahier photocopié pour chaque élève : quatre pages au plus, sans retirer d'activité.
            assert len(pypdf.PdfReader(io.BytesIO(pdf)).pages) <= 4


@pytest.mark.parametrize("code", ["4E-01", "4E-02", "3E-01", "3E-02"])
def test_ressources_completes_et_liens_verifies(code):
    r = charger_ressources()[code]
    assert verifier_ressources(r) == []
    assert r["listening"]["url"], "chaque séance a une écoute en ligne"
    for res in [r["listening"], *r["go_further"]]:
        assert res["url"].startswith("https://learnenglishteens.britishcouncil.org/")


@pytest.mark.parametrize("niveau,filename", CASES)
def test_ecoute_en_ligne_et_script_de_secours_reserve_a_l_animateur(niveau, filename):
    seance = charger_seance(ROOT / niveau / filename)
    r = charger_ressources()[seance.code]
    ecoute = r["listening"]
    eleve, liens_eleve = _lire(produire_pdf(generer_pack_eleve(seance), "eleve"))
    animateur, liens_animateur = _lire(produire_pdf(generer_pack_animateur(seance), "animateur"))

    attendus = {ecoute["url"], *(res["url"] for res in r["go_further"])}
    assert attendus <= set(liens_eleve)
    assert ecoute["url"] in liens_animateur
    # Le script de secours donne les réponses : il n'est imprimé que dans le guide animateur.
    premiere_replique = " ".join(ecoute["fallback"].split("\n")[0].split(":", 1)[-1].split())
    assert premiere_replique not in eleve
    assert premiere_replique in animateur
    assert all(" ".join(q.split()) in eleve for q in ecoute["questions"])


def test_ressources_incompletes_refusees():
    r = dict(charger_ressources()["4E-01"])
    del r["can_do"]
    r["visual"] = [{"label": "X", "picto": "inconnu"}] * 4
    erreurs = verifier_ressources(r)
    assert erreurs == ["Champ manquant : can_do"]
    r["can_do"] = []
    assert any("pictogramme" in e for e in verifier_ressources(r))


def test_public_inconnu_refuse():
    with pytest.raises(ValueError):
        produire_pdf({}, "inconnu")


def test_ressources_absentes_refusees():
    with pytest.raises(ValueError, match="Ressources pédagogiques"):
        produire_pdf({"code": "MISSING"}, "eleve")
