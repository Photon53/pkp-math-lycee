"""Création en masse des comptes professeurs (ticket #22) : l'administrateur télécharge un modèle Excel, le
remplit (une ligne par professeur : nom, e-mail, matières) et l'importe.

Comme pour les familles : une vérification qui n'écrit rien, puis l'import, tout ou rien. Une adresse déjà
inscrite est ignorée (réimporter le fichier ne crée pas de doublon, ne change ni le mot de passe ni les
droits du compte existant). L'import ne crée que des comptes « professeur » : un administrateur se nomme
à la main, depuis sa fiche (second facteur obligatoire).
"""

from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import permissions
from app.db import models
from app.import_familles import TAILLE_MAX_MO, FichierInvalide, _message, _simplifier, _texte
from app.referentiel import Role
from app.schemas_admin import EnseignantEdition
from app.security import generer_mot_de_passe_provisoire, hacher_mot_de_passe_provisoire

LIGNES_MAX = 300
FEUILLE = "Professeurs"
COLONNES = [
    ("nom", "Nom affiché (obligatoire, ex. : Mme Martin)", 34),
    ("email", "E-mail (obligatoire)", 34),
    ("maths", "Enseigne les maths (oui/non)", 16),
    ("anglais", "Enseigne l'anglais (oui/non)", 16),
    ("referent", "Référent anglais (oui/non)", 16),
]
_OUI = {"oui", "o", "x", "1", "vrai", "yes", "y"}
_NON = {"", "non", "n", "0", "faux", "no"}


# --- Modèle à remplir ------------------------------------------------------------------------------------


def modele() -> bytes:
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = FEUILLE
    entete, fond = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E79")
    for i, (_, titre, largeur) in enumerate(COLONNES, start=1):
        cellule = feuille.cell(row=1, column=i, value=titre)
        cellule.font, cellule.fill = entete, fond
        cellule.alignment = Alignment(wrap_text=True, vertical="center")
        feuille.column_dimensions[cellule.column_letter].width = largeur
    feuille.row_dimensions[1].height = 32
    feuille.freeze_panes = "A2"
    oui_non = DataValidation(type="list", formula1='"oui,non"', allow_blank=True)
    feuille.add_data_validation(oui_non)
    oui_non.add(f"C2:E{LIGNES_MAX + 1}")

    aide = classeur.create_sheet("Mode d'emploi")
    aide.column_dimensions["A"].width = 110
    for i, texte in enumerate(
        [
            "Création en masse des comptes professeurs",
            "",
            "1. Une ligne par professeur, dans la feuille « Professeurs ». Ne modifiez pas la première ligne (titres).",
            "2. Nom affiché et e-mail sont obligatoires. L'e-mail sert d'identifiant de connexion.",
            "3. Matières : « oui » ou « non ». Sans rien d'indiqué, le professeur enseigne les maths.",
            "4. Référent anglais : valide les séances d'anglais des collègues (il doit enseigner l'anglais).",
            "",
            "Dans Boussole, onglet Professeurs → « Importer (Excel) » : la vérification signale chaque ligne à corriger",
            "sans rien enregistrer ; l'import crée ensuite tous les comptes, ou aucun si une ligne reste en erreur.",
            "Une adresse déjà inscrite est ignorée. À la fin, transmettez à chacun son mot de passe provisoire :",
            "il le changera à la première connexion. Les classes s'ouvrent ensuite (par le professeur ou l'admin).",
        ],
        start=1,
    ):
        aide.cell(row=i, column=1, value=texte).font = Font(bold=i == 1, size=13 if i == 1 else 11)

    flux = BytesIO()
    classeur.save(flux)
    return flux.getvalue()


# --- Lecture ---------------------------------------------------------------------------------------------


def _cle_colonne(titre: str) -> str | None:
    t = _simplifier(titre)
    if "referent" in t:
        return "referent"
    if "mail" in t:
        return "email"
    if "anglais" in t:
        return "anglais"
    if "math" in t:
        return "maths"
    if t.startswith("nom"):
        return "nom"
    return None


def lire(contenu: bytes) -> list[tuple[int, dict[str, str]]]:
    if len(contenu) > TAILLE_MAX_MO * 1024 * 1024:
        raise FichierInvalide(f"Fichier trop lourd (au plus {TAILLE_MAX_MO} Mo).")
    try:
        classeur = load_workbook(BytesIO(contenu), read_only=True, data_only=True)
    except Exception as e:
        raise FichierInvalide("Ce fichier n'est pas un classeur Excel (.xlsx). Partez du modèle à télécharger.") from e
    feuille = classeur[FEUILLE] if FEUILLE in classeur.sheetnames else classeur.worksheets[0]
    lignes = feuille.iter_rows(values_only=True)
    colonnes: dict[str, int] = {}
    for i, titre in enumerate(next(lignes, None) or ()):
        cle = _cle_colonne(_texte(titre)) if titre else None
        if cle and cle not in colonnes:
            colonnes[cle] = i
    if not {"nom", "email"} <= colonnes.keys():
        classeur.close()
        raise FichierInvalide("Colonnes « Nom » et « E-mail » introuvables : partez du modèle des professeurs.")
    resultat = []
    for numero, valeurs in enumerate(lignes, start=2):
        ligne = {cle: _texte(valeurs[i]) if i < len(valeurs) else "" for cle, i in colonnes.items()}
        if not any(ligne.values()):
            continue
        resultat.append((numero, ligne))
        if len(resultat) > LIGNES_MAX:
            classeur.close()
            raise FichierInvalide(f"Au plus {LIGNES_MAX} professeurs par import : découpez le fichier.")
    classeur.close()
    if not resultat:
        raise FichierInvalide("Aucun professeur dans le fichier : remplissez une ligne par professeur sous les titres.")
    return resultat


# --- Vérification et import ------------------------------------------------------------------------------


class LigneProfesseur(BaseModel):
    ligne: int
    nom: str
    email: str
    matieres: list[str] = []
    erreurs: list[str] = []
    deja_present: bool = False


class ProfesseurCree(BaseModel):
    id: int
    nom: str
    email: str
    mot_de_passe_provisoire: str


class RapportProfesseurs(BaseModel):
    simulation: bool
    lignes: list[LigneProfesseur]
    nb_professeurs: int
    nb_deja_presents: int
    nb_erreurs: int
    comptes: list[ProfesseurCree] = []


def _booleen(valeur: str, defaut: bool, libelle: str, erreurs: list[str]) -> bool:
    v = _simplifier(valeur)
    if v in _OUI:
        return True
    if v in _NON:
        return defaut if not v else False
    erreurs.append(f"{libelle} : « {valeur} » — écrivez oui ou non.")
    return defaut


def _verifier(session: Session, lignes) -> list[tuple[LigneProfesseur, EnseignantEdition | None]]:
    inscrits = set(session.scalars(select(func.lower(models.Enseignant.email))))
    vus: set[str] = set()
    resultat = []
    for numero, brut in lignes:
        erreurs: list[str] = []
        vue = LigneProfesseur(ligne=numero, nom=brut.get("nom", "") or "—", email=brut.get("email", ""))
        anglais = _booleen(brut.get("anglais", ""), False, "Anglais", erreurs)
        # Sans aucune matière indiquée, le professeur enseigne les maths (comme le formulaire).
        maths = _booleen(brut.get("maths", ""), not anglais, "Maths", erreurs)
        referent = _booleen(brut.get("referent", ""), False, "Référent anglais", erreurs)
        edition = None
        if not brut.get("nom"):
            erreurs.append("Nom manquant.")
        if not brut.get("email"):
            erreurs.append("E-mail manquant.")
        if brut.get("nom") and brut.get("email") and not erreurs:
            try:
                edition = EnseignantEdition(
                    nom=brut["nom"], email=brut["email"], role=Role.ENSEIGNANT,
                    enseigne_maths=maths, enseigne_anglais=anglais, referent_anglais=referent,
                )
                vue.email = edition.email
            except ValidationError as e:
                erreurs.append(_message(e))
        if edition is not None:
            vue.matieres = [m for m, oui in (("Maths", maths), ("Anglais", anglais), ("Référent anglais", referent)) if oui]
            if edition.email in vus:
                erreurs.append("Cette adresse figure déjà plus haut dans le fichier.")
            elif edition.email in inscrits:
                vue.deja_present = True
            vus.add(edition.email)
        vue.erreurs = erreurs
        resultat.append((vue, edition))
    return resultat


def importer(session: Session, contenu: bytes, simulation: bool, admin: models.Enseignant) -> RapportProfesseurs:
    """Vérifie toujours tout ; n'écrit que si `simulation` est faux et qu'aucune ligne n'est en erreur. La
    transaction n'est pas validée ici : la route journalise puis valide."""
    verifiees = _verifier(session, lire(contenu))
    a_creer = [(vue, ed) for vue, ed in verifiees if not vue.erreurs and not vue.deja_present]
    rapport = RapportProfesseurs(
        simulation=simulation, lignes=[vue for vue, _ in verifiees], nb_professeurs=len(a_creer),
        nb_deja_presents=sum(1 for vue, _ in verifiees if vue.deja_present),
        nb_erreurs=sum(1 for vue, _ in verifiees if vue.erreurs),
    )
    if simulation or rapport.nb_erreurs:
        return rapport

    for vue, ed in a_creer:
        provisoire = generer_mot_de_passe_provisoire()
        # Coût de hachage modéré pour un secret tiré au hasard ; re-haché au coût complet à la première connexion.
        e = models.Enseignant(
            nom=ed.nom.strip(), email=ed.email, role=Role.ENSEIGNANT,
            enseigne_maths=False, enseigne_anglais=False, referent_anglais=False,
            mot_de_passe_hash=hacher_mot_de_passe_provisoire(provisoire), mdp_provisoire=True,
        )
        session.add(e)
        try:
            permissions.appliquer(
                session, e,
                permissions.depuis_cases([], enseigne_maths=ed.enseigne_maths, enseigne_anglais=ed.enseigne_anglais,
                                         referent_anglais=ed.referent_anglais),
                admin,
            )
        except permissions.HabilitationRefusee as erreur:
            vue.erreurs.append(str(erreur))
            continue
        session.flush()
        rapport.comptes.append(ProfesseurCree(id=e.id, nom=e.nom, email=e.email, mot_de_passe_provisoire=provisoire))
    rapport.nb_erreurs = sum(1 for vue, _ in verifiees if vue.erreurs)
    if rapport.nb_erreurs:  # domaine désactivé entre-temps… : rien n'est enregistré
        session.rollback()
        rapport.comptes = []
    return rapport
