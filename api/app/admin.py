"""Administration des comptes enseignant (aucune route web ne permet d'en créer).

Usage, depuis `api/` (ou `docker compose exec api python -m app.admin …`) :
    python -m app.admin creer --email prof@lycee.fr --nom "Mme Martin"
    python -m app.admin mot-de-passe --email prof@lycee.fr
Le mot de passe est demandé au clavier, jamais passé en argument (historique du shell).
Sans terminal, il est lu sur l'entrée standard (une ligne).
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.security import hacher_mot_de_passe

LONGUEUR_MIN = 12


class ErreurAdmin(ValueError):
    pass


def _verifier_mot_de_passe(mot_de_passe: str) -> None:
    if len(mot_de_passe) < LONGUEUR_MIN:
        raise ErreurAdmin(f"Le mot de passe doit faire au moins {LONGUEUR_MIN} caractères.")


def creer_enseignant(session: Session, email: str, nom: str, mot_de_passe: str) -> models.Enseignant:
    email = email.strip().lower()
    _verifier_mot_de_passe(mot_de_passe)
    if session.scalar(select(models.Enseignant).where(models.Enseignant.email == email)):
        raise ErreurAdmin(f"Un compte existe déjà pour {email}.")
    enseignant = models.Enseignant(email=email, nom=nom.strip(), mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe))
    session.add(enseignant)
    session.commit()
    return enseignant


def changer_mot_de_passe(session: Session, email: str, mot_de_passe: str) -> None:
    _verifier_mot_de_passe(mot_de_passe)
    enseignant = session.scalar(select(models.Enseignant).where(models.Enseignant.email == email.strip().lower()))
    if enseignant is None:
        raise ErreurAdmin(f"Aucun compte pour {email}.")
    enseignant.mot_de_passe_hash = hacher_mot_de_passe(mot_de_passe)
    session.commit()


def _demander_mot_de_passe() -> str:
    if not sys.stdin.isatty():
        # Sans terminal (script, `docker compose exec -T`) : une ligne lue sur
        # l'entrée standard. Sinon getpass attendrait la console indéfiniment.
        return sys.stdin.readline().rstrip("\r\n")
    premier = getpass.getpass("Mot de passe : ")
    if premier != getpass.getpass("Confirmation : "):
        raise ErreurAdmin("Les deux saisies diffèrent.")
    return premier


def main() -> None:
    parser = argparse.ArgumentParser(description="Comptes enseignant PKP Math Lycée")
    commandes = parser.add_subparsers(dest="commande", required=True)
    creer = commandes.add_parser("creer", help="créer un compte enseignant")
    creer.add_argument("--email", required=True)
    creer.add_argument("--nom", required=True)
    mdp = commandes.add_parser("mot-de-passe", help="changer le mot de passe d'un enseignant")
    mdp.add_argument("--email", required=True)
    args = parser.parse_args()

    from app.db.session import SessionLocale

    try:
        with SessionLocale() as session:
            if args.commande == "creer":
                enseignant = creer_enseignant(session, args.email, args.nom, _demander_mot_de_passe())
                print(f"Compte créé pour {enseignant.email}.")
            else:
                changer_mot_de_passe(session, args.email, _demander_mot_de_passe())
                print(f"Mot de passe changé pour {args.email}.")
    except ErreurAdmin as exc:
        sys.exit(f"Erreur : {exc}")


if __name__ == "__main__":
    main()
