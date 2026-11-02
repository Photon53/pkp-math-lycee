import pytest

from pkp_anglais import Etape, Fiche, Seance, generer_pack_animateur, generer_pack_eleve, verifier_seance


def seance_valide():
    return Seance(
        code="4E-01", niveau="4e", titre="Daily life", objectif="Parler de sa routine",
        etapes=(Etape("Échange", 30, "Présente ta routine.", "Faire parler les binômes."),
                Etape("Activités", 60, "Complète les exercices.", "Adapter selon les acquis.")),
        fiches=(Fiche("A", "I ... breakfast.", "have"),
                Fiche("B", "Describe your morning.", "Example: I get up at seven."),
                Fiche("C", "Compare two routines.", "Use whereas or while.")),
    )


def test_seance_valide():
    assert verifier_seance(seance_valide()) == []


def test_duree_incorrecte():
    s = seance_valide()
    from dataclasses import replace
    assert any("90 minutes" in e for e in verifier_seance(replace(s, etapes=s.etapes[:1])))


def test_pack_eleve_sans_corriges_ni_consignes_animateur():
    pack = generer_pack_eleve(seance_valide())
    assert all("corrige" not in f for f in pack["fiches"])
    assert all("consigne_animateur" not in e for e in pack["etapes"])
    assert "have" not in str(pack)


def test_pack_animateur_contient_corriges():
    pack = generer_pack_animateur(seance_valide())
    assert pack["fiches"][0]["corrige"] == "have"


def test_parcours_incomplet_refuse():
    from dataclasses import replace
    s = seance_valide()
    with pytest.raises(ValueError):
        generer_pack_eleve(replace(s, fiches=s.fiches[:2]))
