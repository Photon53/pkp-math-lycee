"""Administration des comptes enseignant (aucune route web ne permet d'en créer).

Usage, depuis `api/` (ou `docker compose exec api python -m app.admin …`) :
    python -m app.admin creer --email prof@lycee.fr --nom "Mme Martin"
    python -m app.admin creer --email admin@pkp.fr --nom "Équipe PKP" --admin
    python -m app.admin mot-de-passe --email prof@lycee.fr
    python -m app.admin promouvoir --email prof@lycee.fr   # compte existant (V1) → administrateur
    python -m app.admin totp --email admin@pkp.fr      # second facteur de l'espace administrateur

Aucun écran ne permet de se donner soi-même le rôle d'administrateur (cahier des charges V2, EA2.2) :
le premier administrateur est créé ici. Les suivants peuvent l'être depuis l'IHM d'administration.
Le mot de passe est demandé au clavier, jamais passé en argument (historique du shell).
Sans terminal, il est lu sur l'entrée standard (une ligne).
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.referentiel import Role
from app.security import generer_secret_totp, hacher_mot_de_passe, uri_totp

LONGUEUR_MIN = 12


class ErreurAdmin(ValueError):
    pass


def _verifier_mot_de_passe(mot_de_passe: str) -> None:
    if len(mot_de_passe) < LONGUEUR_MIN:
        raise ErreurAdmin(f"Le mot de passe doit faire au moins {LONGUEUR_MIN} caractères.")


def creer_enseignant(session: Session, email: str, nom: str, mot_de_passe: str, admin: bool = False) -> models.Enseignant:
    email = email.strip().lower()
    _verifier_mot_de_passe(mot_de_passe)
    if session.scalar(select(models.Enseignant).where(models.Enseignant.email == email)):
        raise ErreurAdmin(f"Un compte existe déjà pour {email}.")
    enseignant = models.Enseignant(
        email=email,
        nom=nom.strip(),
        mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe),
        role=Role.ADMIN if admin else Role.ENSEIGNANT,
    )
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


def promouvoir(session: Session, email: str) -> models.Enseignant:
    """Donne le rôle d'administrateur à un compte existant (passage de la V1 à la V2)."""
    enseignant = session.scalar(select(models.Enseignant).where(models.Enseignant.email == email.strip().lower()))
    if enseignant is None:
        raise ErreurAdmin(f"Aucun compte pour {email}.")
    enseignant.role = Role.ADMIN
    enseignant.actif = True
    session.commit()
    return enseignant


def configurer_totp(session: Session, email: str) -> str:
    """Nouveau secret TOTP pour un administrateur ; renvoie l'URI à charger dans l'application."""
    enseignant = session.scalar(select(models.Enseignant).where(models.Enseignant.email == email.strip().lower()))
    if enseignant is None:
        raise ErreurAdmin(f"Aucun compte pour {email}.")
    if enseignant.role != Role.ADMIN:
        raise ErreurAdmin(f"{email} n'est pas administrateur.")
    enseignant.totp_secret = generer_secret_totp()
    session.commit()
    return uri_totp(enseignant.totp_secret, enseignant.email)


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
    creer.add_argument("--admin", action="store_true", help="donner le rôle d'administrateur")
    mdp = commandes.add_parser("mot-de-passe", help="changer le mot de passe d'un enseignant")
    mdp.add_argument("--email", required=True)
    totp = commandes.add_parser("totp", help="(re)configurer le second facteur d'un administrateur")
    totp.add_argument("--email", required=True)
    promo = commandes.add_parser("promouvoir", help="donner le rôle d'administrateur à un compte existant")
    promo.add_argument("--email", required=True)
    args = parser.parse_args()

    from app.db.session import SessionLocale

    try:
        with SessionLocale() as session:
            if args.commande == "creer":
                enseignant = creer_enseignant(session, args.email, args.nom, _demander_mot_de_passe(), args.admin)
                print(f"Compte {'administrateur' if args.admin else 'enseignant'} créé pour {enseignant.email}.")
            elif args.commande == "promouvoir":
                print(f"{promouvoir(session, args.email).email} est maintenant administrateur.")
            elif args.commande == "totp":
                uri = configurer_totp(session, args.email)
                print("Ajoutez ce compte dans votre application d'authentification (Aegis, Google Authenticator…) :")
                print(uri)
                print("L'ancien secret, s'il existait, ne fonctionne plus.")
            else:
                changer_mot_de_passe(session, args.email, _demander_mot_de_passe())
                print(f"Mot de passe changé pour {args.email}.")
    except ErreurAdmin as exc:
        sys.exit(f"Erreur : {exc}")


if __name__ == "__main__":
    main()
