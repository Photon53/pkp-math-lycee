"""Circuit commun des contenus versionnés (#215) : anglais (séances) et français (dossiers), et toute nouvelle matière.

Un contenu versionné a des `versions`, ordonnées par numéro ; la version courante est la dernière, la version diffusée
est la dernière validée. Chaque version porte `statut`, `auteur_id`, `validateur`, `decide_le` et `motif_refus`.

Règles partagées, sans exception par matière :
- seule une version « soumis » se valide ou se refuse ;
- jamais par son auteur (pas d'auto-validation, règle E0.2 / EX.9-bis) ;
- valider archive l'ancienne version validée : la nouvelle la remplace dans la diffusion ;
- refuser exige un motif et laisse en place la version validée déjà diffusée.

Le contrôle de qualification (validateur habilité dans le domaine et le niveau) reste dans `permissions` ; la
journalisation, dans la route qui appelle ces fonctions.
"""
# Issue #215 — Standardiser l'ajout d'une matière (Claude)

from datetime import UTC, datetime

STATUTS = ("brouillon", "soumis", "valide", "refuse", "archive")
AUTO_VALIDATION = "Vous ne pouvez pas valider votre propre contenu : un autre validateur doit le faire."


def peut_decider(version, qui) -> str | None:
    """Motif du refus d'agir, ou None."""
    if version.statut != "soumis":
        return "Seule une version soumise peut être validée ou refusée."
    if version.auteur_id is not None and version.auteur_id == qui.id:
        return AUTO_VALIDATION
    return None


def valider(contenu, qui) -> None:
    for v in contenu.versions[:-1]:
        if v.statut == "valide":
            v.statut = "archive"  # conservée dans l'historique, plus diffusée
    c = contenu.courante
    c.statut, c.validateur, c.decide_le, c.motif_refus = "valide", qui, datetime.now(UTC), None


def refuser(contenu, qui, motif: str) -> None:
    c = contenu.courante
    c.statut, c.validateur, c.decide_le, c.motif_refus = "refuse", qui, datetime.now(UTC), motif


def diffusee(contenu):
    """La dernière version validée, seule servie aux élèves ; None tant qu'aucune ne l'est."""
    return next((v for v in reversed(contenu.versions) if v.statut == "valide"), None)
