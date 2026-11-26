"""Contrôles d'une base avant la mise en service en production (#116).

Usage, depuis `api/` : `python -m app.production verifier`
Code de sortie 1 si un problème est trouvé : l'étape de préparation échoue et l'API ne démarre pas.
Les avertissements sont affichés sans bloquer : ils appellent une vérification de l'administrateur.
Lecture seule : rien n'est modifié ni supprimé.
"""
# Issue #116 — Verrouillage du mode production (Claude)

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.db.seed import EMAIL_ADMIN_DEMO, EMAIL_ANGLAIS_DEMO, EMAIL_DEMO

EMAILS_DEMO = (EMAIL_DEMO, EMAIL_ADMIN_DEMO, EMAIL_ANGLAIS_DEMO)


def problemes(session: Session) -> list[str]:
    """Comptes de la démonstration présents : leurs mots de passe et les codes de leurs élèves sont publics."""
    presents = sorted(session.scalars(select(models.Enseignant.email).where(models.Enseignant.email.in_(EMAILS_DEMO))))
    return [
        f"Compte de démonstration présent : {email} (mot de passe et codes élèves publiés dans app/db/seed.py). "
        "Supprimer la démonstration ou utiliser une base de production vierge."
        for email in presents
    ]


def avertissements(session: Session) -> list[str]:
    """Classes actives rangées dans un domaine fermé au public et absentes des classes pilotes (#176, SEC-D6) :
    leurs élèves n'ont plus accès au contenu. Comptes par domaine seulement, aucune donnée nominative."""
    pilotes = select(models.ClassePilote.classe_id)
    lignes = session.execute(
        select(models.Classe.domaine_code, func.count())
        .join(models.DomainePedagogique, models.DomainePedagogique.code == models.Classe.domaine_code)
        .where(models.DomainePedagogique.public.is_(False), models.Classe.archivee_le.is_(None),
               models.Classe.id.not_in(pilotes))
        .group_by(models.Classe.domaine_code)
        .order_by(models.Classe.domaine_code)
    ).all()
    return [
        f"{nombre} classe(s) active(s) du domaine fermé {domaine} hors des classes pilotes : leurs élèves n'ont plus "
        "accès au contenu (SEC-D6). Les inscrire comme classes pilotes, les archiver ou ouvrir le domaine."
        for domaine, nombre in lignes
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Contrôles de la base avant la mise en service en production")
    parser.add_argument("commande", choices=["verifier"])
    parser.parse_args()
    from app.db.session import SessionLocale

    with SessionLocale() as session:
        trouves = problemes(session)
        a_verifier = avertissements(session)
    for avertissement in a_verifier:
        print(f"AVERTISSEMENT : {avertissement}", file=sys.stderr)
    for probleme in trouves:
        print(f"REFUS : {probleme}", file=sys.stderr)
    if trouves:
        sys.exit(1)
    print("Base prête pour la production : aucun compte de démonstration.")


if __name__ == "__main__":
    main()
