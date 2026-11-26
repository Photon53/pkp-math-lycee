# Issue #4 — Renforcer le contrôle des PDF (Claude)
"""Contrôle renforcé des PDF (#4) : PDF ordinaires, malformés, chiffrés, à contenu actif ; limites de taille, de
pages, de mémoire et de durée ; aucun fichier refusé n'est publié."""

import importlib.util
import os

import pytest

from app import controle_pdf
from app.config import settings
from tests import pdf_exemples
from tests.conftest import connecter_eleve, connecter_enseignant
from tests import test_v2_administration as v2

ACCEPTES = {
    "page blanche": pdf_exemples.ordinaire,
    "texte, signet, liens interne et web": pdf_exemples.avec_texte_et_liens,
    "ouverture sur une page": pdf_exemples.ouverture_sur_une_page,
    "PDF balisé (/S de structure)": pdf_exemples.structure_balisee,
    "lien https": lambda: pdf_exemples.lien("https://eduscol.education.fr/"),
    "lien mailto": lambda: pdf_exemples.lien("mailto:prof@exemple.fr"),
}

REFUSES = {
    "JavaScript de document": (pdf_exemples.javascript_nomme, "JavaScript"),
    "JavaScript à l'ouverture": (pdf_exemples.javascript_a_l_ouverture, "action à l'ouverture"),
    "JavaScript sous un nom encodé": (pdf_exemples.javascript_nom_encode, "JavaScript"),
    "JavaScript dans un flux d'objets compressé": (pdf_exemples.javascript_dans_un_flux_d_objets, "JavaScript"),
    "JavaScript orphelin": (pdf_exemples.javascript_orphelin, "JavaScript"),
    "lancement de programme": (pdf_exemples.lancement, "Launch"),
    "envoi de formulaire": (pdf_exemples.envoi_formulaire, "SubmitForm"),
    "actions automatiques": (pdf_exemples.actions_automatiques, "actions automatiques"),
    "fichier embarqué": (pdf_exemples.fichier_embarque, "fichiers"),
    "lien javascript:": (lambda: pdf_exemples.lien("javascript:app.alert(1)"), "lien"),
    "lien file:": (lambda: pdf_exemples.lien("file:///etc/passwd"), "lien"),
    "chiffré": (pdf_exemples.chiffre, "mot de passe"),
    "tronqué": (pdf_exemples.tronque, "lisible"),
    "en-tête seul": (pdf_exemples.faux_entete, "lisible"),
    "sans page": (pdf_exemples.sans_page, "lisible"),
    "pas un PDF": (lambda: b"MZ\x90\x00 executable", "lisible"),
}


@pytest.mark.parametrize("fabrique_pdf", ACCEPTES.values(), ids=ACCEPTES.keys())
def test_pdf_ordinaires_acceptes(fabrique_pdf):
    assert controle_pdf.analyser(fabrique_pdf()) == controle_pdf.Verdict(True)


@pytest.mark.parametrize(("fabrique_pdf", "motif"), REFUSES.values(), ids=REFUSES.keys())
def test_pdf_dangereux_ou_malformes_refuses(fabrique_pdf, motif):
    verdict = controle_pdf.analyser(fabrique_pdf())
    assert not verdict.accepte
    assert motif in verdict.motif


def test_le_contenu_actif_echappait_a_l_ancienne_recherche_de_chaines():
    """Régression de l'audit : ces PDF ne contiennent ni « /JavaScript » ni « /JS » en clair."""
    for fabrique_pdf in (pdf_exemples.javascript_nom_encode, pdf_exemples.javascript_dans_un_flux_d_objets):
        contenu = fabrique_pdf()
        assert b"/JavaScript" not in contenu and b"/JS " not in contenu
        assert not controle_pdf.analyser(contenu).accepte


def test_limite_de_pages(monkeypatch):
    monkeypatch.setattr(controle_pdf, "PAGES_MAX", 2)
    assert controle_pdf.analyser(pdf_exemples.ordinaire(2)).accepte
    verdict = controle_pdf.analyser(pdf_exemples.ordinaire(3))
    assert not verdict.accepte and "2 pages" in verdict.motif


def test_limite_d_objets(monkeypatch):
    monkeypatch.setattr(controle_pdf, "OBJETS_MAX", 3)
    assert controle_pdf.analyser(pdf_exemples.avec_texte_et_liens()) == controle_pdf.Verdict(False, controle_pdf.MOTIF_TROP_LONG)


class TestIsolement:
    """L'analyse tourne dans un processus séparé, borné en durée et en mémoire."""

    def test_verdict_rendu_par_le_processus_d_analyse(self):
        controle_pdf.analyser_isole(pdf_exemples.ordinaire())
        with pytest.raises(controle_pdf.PdfRefuse, match="JavaScript"):
            controle_pdf.analyser_isole(pdf_exemples.javascript_dans_un_flux_d_objets())

    def test_duree_depassee_refusee_et_processus_arrete(self, monkeypatch):
        monkeypatch.setattr(controle_pdf, "DUREE_MAX_S", 0)
        with pytest.raises(controle_pdf.PdfRefuse, match="trop long"):
            controle_pdf.analyser_isole(pdf_exemples.ordinaire())
        import multiprocessing

        assert not [p for p in multiprocessing.active_children() if p.is_alive()]

    @pytest.mark.skipif(importlib.util.find_spec("resource") is None or os.name == "nt", reason="limites POSIX")
    def test_memoire_depassee_refusee(self, monkeypatch):
        """Le processus d'analyse ne peut pas réserver plus que la limite : il meurt, et le PDF est refusé."""
        monkeypatch.setattr(controle_pdf, "MEMOIRE_MAX_MO", 1)
        with pytest.raises(controle_pdf.PdfRefuse, match="trop long ou trop complexe"):
            controle_pdf.analyser_isole(pdf_exemples.avec_texte_et_liens())


class TestPublication:
    """Par l'API : un PDF refusé n'est jamais écrit sur disque ni servi ; le fichier accepté reste intact."""

    aides = v2.TestRessources()

    def _pdf(self, client, h) -> int:
        return self.aides._pdf(client, h, self.aides._competence_ouverte(client))

    def _fichiers(self):
        from pathlib import Path

        dossier = Path(settings.dossier_fichiers)
        return set(dossier.iterdir()) if dossier.exists() else set()

    @pytest.mark.parametrize("fabrique_pdf", [f for f, _ in REFUSES.values()][:6] + [pdf_exemples.chiffre, pdf_exemples.tronque])
    def test_pdf_refuse_jamais_publie(self, client, fabrique_pdf):
        h = connecter_enseignant(client)
        rid = self._pdf(client, h)
        avant = self._fichiers()
        envoi = client.put(f"/enseignants/ressources/{rid}/fichier", headers={**h, "Content-Type": "application/pdf"}, content=fabrique_pdf())
        assert envoi.status_code == 422, envoi.text
        assert self._fichiers() == avant
        assert client.get(f"/ressources/{rid}/fichier", headers=connecter_eleve(client)).status_code == 404

    def test_pdf_refuse_ne_remplace_pas_le_fichier_publie(self, client):
        h = connecter_enseignant(client)
        rid = self._pdf(client, h)
        h = {**h, "Content-Type": "application/pdf"}
        bon = pdf_exemples.avec_texte_et_liens()
        assert client.put(f"/enseignants/ressources/{rid}/fichier", headers=h, content=bon).status_code == 200
        assert client.put(f"/enseignants/ressources/{rid}/fichier", headers=h, content=pdf_exemples.lancement()).status_code == 422
        assert client.get(f"/ressources/{rid}/fichier", headers=connecter_eleve(client)).content == bon


def test_reanalyse_des_pdf_deja_deposes(client, session):
    """`python -m app.ressources verifier-pdf` : signale un PDF déposé avant le contrôle, sans rien modifier."""
    from pathlib import Path

    from app import ressources

    aides = v2.TestRessources()
    h = connecter_enseignant(client)
    sain, piege = (aides._pdf(client, h, aides._competence_ouverte(client)) for _ in range(2))
    entete_pdf = {**h, "Content-Type": "application/pdf"}
    for rid in (sain, piege):
        assert client.put(f"/enseignants/ressources/{rid}/fichier", headers=entete_pdf, content=pdf_exemples.ordinaire()).status_code == 200
    # Fichier piégé déposé avant le contrôle renforcé : simulé en remplaçant le fichier sur disque.
    from app.db import models

    r = session.get(models.Ressource, piege)
    chemin = Path(settings.dossier_fichiers) / r.fichier
    chemin.write_bytes(pdf_exemples.javascript_dans_un_flux_d_objets())
    signales = ressources.verifier_pdf_deposes(session)
    assert [(x.id, "JavaScript" in motif) for x, motif in signales] == [(piege, True)]
    assert chemin.is_file() and not session.get(models.Ressource, piege).masquee
