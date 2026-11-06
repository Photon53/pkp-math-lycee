"""Inscription en masse : l'administrateur télécharge un modèle Excel, le remplit (une ligne par enfant) et
l'importe. Les enfants d'une même adresse e-mail forment une famille ; le second responsable légal, s'il est
indiqué, suit les mêmes enfants. La classe de maths et le groupe d'anglais sont facultatifs.

L'import se fait en deux temps : une vérification qui n'écrit rien (chaque ligne avec ses erreurs), puis
l'import lui-même, tout ou rien. Un enfant déjà présent dans la famille (même prénom, même nom) est ignoré :
réimporter le même fichier ne crée pas de doublon.
"""

import unicodedata
from dataclasses import dataclass, field
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from pkp_engine import Niveau
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enfants, parents
from app.db import models
from app.schemas import CarteEnfant, EnfantSaisi, ParentCreation

TAILLE_MAX_MO = 2
LIGNES_MAX = 1000
ELEVES_PAR_GROUPE = 30  # même limite que l'ajout d'enfants à un groupe

FEUILLE = "Élèves"
COLONNES = [
    ("prenom", "Prénom (obligatoire)", 18),
    ("nom", "Nom", 18),
    ("niveau", "Niveau (obligatoire)", 12),
    ("email1", "E-mail du parent 1 (obligatoire)", 32),
    ("email2", "E-mail du parent 2", 32),
    ("classes", "Classe de maths (code)", 22),
    ("groupe", "Groupe d'anglais", 30),
]
_NIVEAUX = {
    "6e": Niveau("6e"), "6eme": Niveau("6e"), "sixieme": Niveau("6e"),
    "5e": Niveau("5e"), "5eme": Niveau("5e"), "cinquieme": Niveau("5e"),
    "4e": Niveau("4e"), "4eme": Niveau("4e"), "quatrieme": Niveau("4e"),
    "3e": Niveau("3e"), "3eme": Niveau("3e"), "troisieme": Niveau("3e"),
    "2nde": Niveau("2nde"), "2de": Niveau("2nde"), "2nd": Niveau("2nde"), "seconde": Niveau("2nde"),
    "1re": Niveau("1re"), "1ere": Niveau("1re"), "1e": Niveau("1re"), "premiere": Niveau("1re"),
    "tle": Niveau("Tle"), "terminale": Niveau("Tle"), "term": Niveau("Tle"),
}


class FichierInvalide(ValueError):
    pass


# --- Modèle à remplir ------------------------------------------------------------------------------------


def _libelle_groupe(g: models.GroupeAnglais) -> str:
    return f"{g.nom} · {g.enseignant.nom}"


def modele(session: Session) -> bytes:
    """Classeur à remplir : la feuille « Élèves », des listes déroulantes (niveaux, classes et groupes
    existants) et un mode d'emploi."""
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = FEUILLE
    entete = Font(bold=True, color="FFFFFF")
    fond = PatternFill("solid", fgColor="1F4E79")
    for i, (_, titre, largeur) in enumerate(COLONNES, start=1):
        cellule = feuille.cell(row=1, column=i, value=titre)
        cellule.font, cellule.fill = entete, fond
        cellule.alignment = Alignment(wrap_text=True, vertical="center")
        feuille.column_dimensions[cellule.column_letter].width = largeur
    feuille.row_dimensions[1].height = 32
    feuille.freeze_panes = "A2"

    listes = classeur.create_sheet("Listes")
    # Seules les classes et groupes actifs sont proposés (V3, Lot 3).
    classes = session.scalars(
        select(models.Classe).where(models.Classe.archivee_le.is_(None)).order_by(models.Classe.code)
    ).all()
    groupes = session.scalars(
        select(models.GroupeAnglais).where(models.GroupeAnglais.archivee_le.is_(None))
        .order_by(models.GroupeAnglais.niveau, models.GroupeAnglais.nom)
    ).all()
    niveaux = [n.value for n in Niveau]
    for colonne, titre, valeurs in (
        (1, "Niveaux", niveaux),
        (2, "Classes de maths", [c.code for c in classes]),
        (3, "Classe : niveau et professeur", [f"{c.niveau.value} · {c.enseignant.nom}" for c in classes]),
        (4, "Groupes d'anglais", [_libelle_groupe(g) for g in groupes]),
        (5, "Groupe : niveau", [g.niveau for g in groupes]),
    ):
        listes.cell(row=1, column=colonne, value=titre).font = Font(bold=True)
        for ligne, valeur in enumerate(valeurs, start=2):
            listes.cell(row=ligne, column=colonne, value=valeur)
        listes.column_dimensions[listes.cell(row=1, column=colonne).column_letter].width = 30

    def deroulante(lettre: str, colonne_liste: str, nombre: int, stricte: bool) -> None:
        if not nombre:
            return
        validation = DataValidation(
            type="list", formula1=f"=Listes!${colonne_liste}$2:${colonne_liste}${nombre + 1}", allow_blank=True,
            showErrorMessage=stricte, errorTitle="Valeur inconnue", error="Choisissez une valeur de la liste.",
        )
        feuille.add_data_validation(validation)
        validation.add(f"{lettre}2:{lettre}{LIGNES_MAX + 1}")

    deroulante("C", "A", len(niveaux), stricte=False)
    # Plusieurs classes possibles (parcours différents), séparées par des virgules : saisie libre acceptée.
    deroulante("F", "B", len(classes), stricte=False)
    deroulante("G", "D", len(groupes), stricte=True)

    aide = classeur.create_sheet("Mode d'emploi")
    aide.column_dimensions["A"].width = 110
    for i, texte in enumerate(
        [
            "Inscription en masse des élèves et de leurs familles",
            "",
            "1. Une ligne par enfant, dans la feuille « Élèves ». Ne modifiez pas la première ligne (titres).",
            "2. Prénom, niveau et e-mail du parent 1 sont obligatoires. Le nom est conseillé (il distingue deux homonymes).",
            "3. Les enfants qui ont le même e-mail de parent 1 forment une famille (frères et sœurs).",
            "4. E-mail du parent 2 (facultatif) : second responsable légal, il suit les mêmes enfants.",
            "5. Classe de maths (facultatif) : code de la classe, de même niveau que l'enfant. Plusieurs parcours :",
            "   séparez les codes par des virgules (ex. : 2NDE-A, 2NDE-EXC).",
            "6. Groupe d'anglais (facultatif) : choisissez-le dans la liste (4e et 3e).",
            "7. Niveaux acceptés : 6e, 5e, 4e, 3e, 2nde, 1re, Tle (ou en toutes lettres : seconde, première…).",
            "",
            "Dans Boussole, onglet Familles → « Importer (Excel) » : la vérification signale chaque ligne à corriger sans",
            "rien enregistrer ; l'import crée ensuite tout, ou rien si une ligne reste en erreur. Un enfant déjà",
            "présent dans la famille (même prénom et même nom) est ignoré : réimporter le fichier ne crée pas de doublon.",
            "À la fin, imprimez les cartes des enfants et transmettez à chaque nouveau parent son mot de passe provisoire.",
        ],
        start=1,
    ):
        aide.cell(row=i, column=1, value=texte).font = Font(bold=i == 1, size=13 if i == 1 else 11)

    flux = BytesIO()
    classeur.save(flux)
    return flux.getvalue()


# --- Lecture du fichier rempli -----------------------------------------------------------------------------


def _simplifier(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.casefold())
    return "".join(c for c in texte if not unicodedata.combining(c)).replace("è", "e")


def _cle_colonne(titre: str) -> str | None:
    t = _simplifier(titre)
    if t.startswith("prenom"):
        return "prenom"
    if t.startswith("nom"):
        return "nom"
    if t.startswith("niveau"):
        return "niveau"
    if "mail" in t:
        return "email2" if "2" in t else "email1"
    if "classe" in t or "math" in t:
        return "classes"
    if "groupe" in t or "anglais" in t:
        return "groupe"
    return None


def _texte(valeur) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, float) and valeur.is_integer():
        valeur = int(valeur)
    return " ".join(str(valeur).split())


def lire(contenu: bytes) -> list[tuple[int, dict[str, str]]]:
    """Lignes non vides de la feuille « Élèves » (ou de la première feuille), avec leur numéro dans Excel."""
    if len(contenu) > TAILLE_MAX_MO * 1024 * 1024:
        raise FichierInvalide(f"Fichier trop lourd (au plus {TAILLE_MAX_MO} Mo).")
    try:
        classeur = load_workbook(BytesIO(contenu), read_only=True, data_only=True)
    except Exception as e:  # zip invalide, autre format…
        raise FichierInvalide("Ce fichier n'est pas un classeur Excel (.xlsx). Partez du modèle à télécharger.") from e
    feuille = classeur[FEUILLE] if FEUILLE in classeur.sheetnames else classeur.worksheets[0]
    lignes = feuille.iter_rows(values_only=True)
    titres = next(lignes, None) or ()
    colonnes = {}
    for i, titre in enumerate(titres):
        cle = _cle_colonne(_texte(titre)) if titre else None
        if cle and cle not in colonnes:
            colonnes[cle] = i
    if not {"prenom", "niveau", "email1"} <= colonnes.keys():
        raise FichierInvalide("Colonnes « Prénom », « Niveau » et « E-mail du parent 1 » introuvables : partez du modèle.")
    resultat = []
    for numero, valeurs in enumerate(lignes, start=2):
        ligne = {cle: _texte(valeurs[i]) if i < len(valeurs) else "" for cle, i in colonnes.items()}
        if not any(ligne.values()):
            continue
        resultat.append((numero, ligne))
        if len(resultat) > LIGNES_MAX:
            raise FichierInvalide(f"Au plus {LIGNES_MAX} élèves par import : découpez le fichier.")
    classeur.close()
    if not resultat:
        raise FichierInvalide("Aucun élève dans le fichier : remplissez une ligne par enfant sous les titres.")
    return resultat


# --- Vérification et import ----------------------------------------------------------------------------------


class LigneImport(BaseModel):
    ligne: int
    enfant: str
    niveau: str | None = None
    parents: list[str] = []
    inscriptions: list[str] = []
    erreurs: list[str] = []
    deja_present: bool = False


class CarteImportee(CarteEnfant):
    famille: str


class CompteParentCree(BaseModel):
    email: str
    mot_de_passe_provisoire: str


class RapportImport(BaseModel):
    simulation: bool
    lignes: list[LigneImport]
    nb_enfants: int
    nb_deja_presents: int
    nb_comptes_nouveaux: int
    nb_erreurs: int
    cartes: list[CarteImportee] = []
    comptes: list[CompteParentCree] = []


@dataclass
class _Ligne:
    vue: LigneImport
    saisi: EnfantSaisi | None = None
    emails: list[str] = field(default_factory=list)
    classes: list[models.Classe] = field(default_factory=list)
    groupe: models.GroupeAnglais | None = None


def _message(err: ValidationError) -> str:
    return err.errors()[0]["msg"].removeprefix("Value error, ")


def _verifier(session: Session, lignes: list[tuple[int, dict[str, str]]]) -> list[_Ligne]:
    classes = {c.code.upper(): c for c in session.scalars(select(models.Classe).where(models.Classe.archivee_le.is_(None)))}
    groupes = list(session.scalars(select(models.GroupeAnglais).where(models.GroupeAnglais.archivee_le.is_(None))))
    comptes = {p.email: p for p in session.scalars(select(models.Parent))}
    vus: set[tuple[str, str, str]] = set()
    par_famille: dict[str, int] = {}
    places = {g.id: len(g.eleves) for g in groupes}
    verifiees = []
    for numero, brut in lignes:
        erreurs: list[str] = []
        vue = LigneImport(ligne=numero, enfant=f"{brut.get('prenom', '')} {brut.get('nom', '')}".strip() or "—")
        ligne = _Ligne(vue=vue)
        verifiees.append(ligne)

        niveau = _NIVEAUX.get(_simplifier(brut.get("niveau", "")).replace(" ", ""))
        if niveau is None:
            erreurs.append(f"Niveau « {brut.get('niveau', '')} » inconnu (6e, 5e, 4e, 3e, 2nde, 1re ou Tle)."
                           if brut.get("niveau") else "Niveau manquant.")
        if not brut.get("prenom"):
            erreurs.append("Prénom manquant.")
        elif niveau is not None:
            try:
                ligne.saisi = EnfantSaisi(prenom=brut["prenom"], nom=brut.get("nom", ""), niveau=niveau)
                vue.enfant, vue.niveau = enfants.nom_affiche(ligne.saisi), niveau.value
            except ValidationError as e:
                erreurs.append(_message(e))

        for cle, obligatoire in (("email1", True), ("email2", False)):
            if not brut.get(cle):
                if obligatoire:
                    erreurs.append("E-mail du parent 1 manquant.")
                continue
            try:
                email = ParentCreation(email=brut[cle]).email
            except ValidationError:
                erreurs.append(f"Adresse e-mail invalide : « {brut[cle]} ».")
                continue
            if email in ligne.emails:
                erreurs.append("Le parent 2 a la même adresse que le parent 1.")
            else:
                ligne.emails.append(email)
        vue.parents = ligne.emails

        for code in filter(None, (c.strip().upper() for c in brut.get("classes", "").replace(";", ",").split(","))):
            classe = classes.get(code)
            if classe is None:
                erreurs.append(f"Classe « {code} » introuvable.")
            elif niveau is not None and classe.niveau != niveau:
                erreurs.append(f"La classe {code} est une classe de {classe.niveau.value}, pas de {niveau.value}.")
            elif classe not in ligne.classes:
                ligne.classes.append(classe)
        if brut.get("groupe"):
            voulu = _simplifier(brut["groupe"])
            trouves = [g for g in groupes if _simplifier(_libelle_groupe(g)) == voulu] or [
                g for g in groupes if _simplifier(g.nom) == voulu
            ]
            if not trouves:
                erreurs.append(f"Groupe d'anglais « {brut['groupe']} » introuvable : choisissez-le dans la liste.")
            elif len(trouves) > 1:
                erreurs.append(f"Plusieurs groupes s'appellent « {brut['groupe']} » : choisissez-le dans la liste.")
            elif niveau is not None and trouves[0].niveau != niveau.value:
                erreurs.append(f"Le groupe « {trouves[0].nom} » est un groupe de {trouves[0].niveau}, pas de {niveau.value}.")
            else:
                ligne.groupe = trouves[0]
        vue.inscriptions = [c.code for c in ligne.classes] + ([f"Anglais : {ligne.groupe.nom}"] if ligne.groupe else [])

        if ligne.saisi and ligne.emails:
            cle = (ligne.emails[0], ligne.saisi.prenom.casefold(), ligne.saisi.nom.casefold())
            existant = comptes.get(ligne.emails[0])
            if cle in vus:
                erreurs.append("Cet enfant figure déjà plus haut dans le fichier, pour la même famille.")
            elif existant and any(
                (e.prenom.casefold(), e.nom.casefold()) == cle[1:] for e in existant.famille
            ):
                vue.deja_present = True
            vus.add(cle)
        if not erreurs and not vue.deja_present:
            for email in ligne.emails:
                deja = len(comptes[email].famille) if email in comptes else 0
                par_famille[email] = par_famille.get(email, deja) + 1
                if par_famille[email] > enfants.MAX_ENFANTS_PAR_FAMILLE:
                    erreurs.append(f"La famille {email} dépasserait {enfants.MAX_ENFANTS_PAR_FAMILLE} enfants.")
            if ligne.groupe:
                places[ligne.groupe.id] += 1
                if places[ligne.groupe.id] > ELEVES_PAR_GROUPE:
                    erreurs.append(f"Le groupe « {ligne.groupe.nom} » dépasserait {ELEVES_PAR_GROUPE} élèves.")
        vue.erreurs = erreurs
    return verifiees


def importer(session: Session, contenu: bytes, simulation: bool) -> RapportImport:
    """Vérifie toujours tout ; n'écrit que si `simulation` est faux et qu'aucune ligne n'est en erreur."""
    verifiees = _verifier(session, lire(contenu))
    nouveaux = {e for lg in verifiees if not lg.vue.deja_present for e in lg.emails} - set(
        session.scalars(select(models.Parent.email))
    )
    rapport = RapportImport(
        simulation=simulation, lignes=[lg.vue for lg in verifiees],
        nb_enfants=sum(1 for lg in verifiees if not lg.vue.erreurs and not lg.vue.deja_present),
        nb_deja_presents=sum(1 for lg in verifiees if lg.vue.deja_present),
        nb_comptes_nouveaux=len(nouveaux), nb_erreurs=sum(1 for lg in verifiees if lg.vue.erreurs),
    )
    if simulation or rapport.nb_erreurs:
        return rapport

    comptes: dict[str, models.Parent] = {}
    for ligne in verifiees:
        if ligne.vue.deja_present:
            continue
        enfant, code = enfants.creer(session, ligne.saisi.prenom, ligne.saisi.nom, ligne.saisi.niveau)
        for email in ligne.emails:
            parent = comptes.get(email) or session.scalar(select(models.Parent).where(models.Parent.email == email))
            if parent is None:
                parent = models.Parent(email=email, mot_de_passe_hash="", mdp_provisoire=True)
                rapport.comptes.append(CompteParentCree(email=email, mot_de_passe_provisoire=parents.reinitialiser(parent)))
                session.add(parent)
            comptes[email] = parent
            parent.famille.append(enfant)
        session.flush()
        try:
            for classe in ligne.classes:
                enfants.inscrire_maths(session, enfant, classe)
            if ligne.groupe:
                enfants.inscrire_anglais(session, enfant, ligne.groupe)
        except enfants.InscriptionImpossible as e:
            ligne.vue.erreurs.append(str(e))
        rapport.cartes.append(CarteImportee(**enfants.carte(enfant, code).model_dump(), famille=ligne.emails[0]))
    rapport.nb_erreurs = sum(1 for lg in verifiees if lg.vue.erreurs)
    if rapport.nb_erreurs:  # homonyme impossible à distinguer dans une classe : rien n'est enregistré
        session.rollback()
        rapport.cartes, rapport.comptes = [], []
    return rapport
