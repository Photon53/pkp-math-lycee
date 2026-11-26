# Issue #4 — Renforcer le contrôle des PDF (Claude)
"""Contrôle renforcé des PDF déposés comme ressources (issue #4, cahier des charges V2 EA5.5).

L'ancienne recherche de chaînes (`/JavaScript`, `/Encrypt`) ne voyait ni les objets compressés dans des flux d'objets,
ni les noms encodés (`/J#61vaScript`), ni les actions autres que JavaScript. Ici, le fichier est analysé par un
analyseur maintenu (pypdf), qui reconstruit chaque objet du document, et confronté à une **liste blanche** :

- autorisé : pages, texte, images, polices, signets, liens internes (`GoTo`), navigation (`Named`), liens web
  (`URI` en http, https ou mailto), formulaires sans script ;
- refusé : PDF chiffré, malformé ou illisible ; toute autre action (`JavaScript`, `Launch`, `SubmitForm`,
  `ImportData`, `GoToR`, `GoToE`, `Rendition`…), actions déclenchées automatiquement (`/AA`), action d'ouverture
  autre qu'un saut de page, fichiers embarqués ou joints, contenus multimédia (`RichMedia`, 3D, son, vidéo),
  formulaires XFA.

Le fichier refusé n'est jamais écrit sur disque : rien n'est publié. Le fichier accepté est conservé tel quel.

Isolement : l'analyse tourne dans un processus séparé (démarrage `spawn`, sans hériter de l'état de l'API), limité
en mémoire et en temps processeur quand le système le permet, et tué au-delà d'une durée maximale. Un nombre maximal
d'analyses simultanées borne la charge. Un PDF qui épuise ces limites est refusé.
"""

import multiprocessing
import threading
from dataclasses import dataclass

# Limites de l'analyse. Un cours ou une fiche ordinaire est très loin de ces valeurs.
DUREE_MAX_S = 15
MEMOIRE_MAX_MO = 512
PAGES_MAX = 500
OBJETS_MAX = 100_000
ANALYSES_SIMULTANEES = 2

ACTIONS_AUTORISEES = {"/GoTo", "/Named", "/URI"}
SCHEMAS_URI_AUTORISES = ("http://", "https://", "mailto:")
# Clés interdites partout dans le document.
CLES_INTERDITES = {
    "/JS": "du JavaScript",
    "/JavaScript": "du JavaScript",
    "/AA": "des actions automatiques",
    "/EmbeddedFile": "des fichiers embarqués",
    "/EmbeddedFiles": "des fichiers embarqués",
    "/RichMedia": "du contenu multimédia",
    "/RichMediaContent": "du contenu multimédia",
    "/XFA": "un formulaire XFA",
}
# Valeurs de /Subtype (annotations) ou de /Type interdites.
TYPES_INTERDITS = {
    "/FileAttachment": "des fichiers joints",
    "/Filespec": "des fichiers joints",
    "/EmbeddedFile": "des fichiers embarqués",
    "/RichMedia": "du contenu multimédia",
    "/Movie": "du contenu multimédia",
    "/Sound": "du contenu multimédia",
    "/Screen": "du contenu multimédia",
    "/3D": "du contenu multimédia",
}

MOTIF_ILLISIBLE = "Ce fichier n'est pas un PDF lisible."
MOTIF_CHIFFRE = "Les PDF protégés par mot de passe ne sont pas acceptés."
MOTIF_TROP_LONG = "Ce PDF est trop long ou trop complexe à analyser."


@dataclass(frozen=True)
class Verdict:
    accepte: bool
    motif: str = ""


class PdfRefuse(Exception):
    """Levée par `analyser_isole` quand le PDF est refusé ; le message s'affiche tel quel."""


def _refus(element: str) -> Verdict:
    return Verdict(False, f"Les PDF contenant {element} ne sont pas acceptés.")


def _cle(valeur) -> str:
    return str(valeur) if valeur is not None else ""


def _verifier_action(action) -> Verdict | None:
    """Une action (dictionnaire /S …) : type de la liste blanche, et adresse web pour /URI."""
    type_action = _cle(action.get("/S"))
    if type_action not in ACTIONS_AUTORISEES:
        if type_action == "/JavaScript":
            return _refus("du JavaScript")
        return _refus(f"une action non autorisée ({type_action.lstrip('/') or 'inconnue'})")
    if type_action == "/URI":
        uri = action.get("/URI")
        texte = uri.decode("latin-1", "replace") if isinstance(uri, bytes) else str(uri or "")
        if not texte.strip().lower().startswith(SCHEMAS_URI_AUTORISES):
            return _refus("un lien d'un type non autorisé")
    return None


def analyser(contenu: bytes) -> Verdict:
    """Analyse complète, dans le processus courant. Appeler plutôt `analyser_isole` depuis l'API."""
    import io
    import logging

    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
    from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    if not contenu.startswith(b"%PDF-"):
        return Verdict(False, MOTIF_ILLISIBLE)
    try:
        lecteur = PdfReader(io.BytesIO(contenu), strict=False)
        if lecteur.is_encrypted:
            return Verdict(False, MOTIF_CHIFFRE)
        if len(lecteur.pages) == 0:
            return Verdict(False, MOTIF_ILLISIBLE)
        if len(lecteur.pages) > PAGES_MAX:
            return Verdict(False, f"Le PDF dépasse {PAGES_MAX} pages.")

        racine = lecteur.trailer["/Root"].get_object()
        ouverture = racine.get("/OpenAction")
        if ouverture is not None:
            ouverture = ouverture.get_object()
            # Une destination (tableau) est un simple saut de page ; une action doit être un /GoTo.
            if isinstance(ouverture, DictionaryObject) and _cle(ouverture.get("/S")) != "/GoTo":
                return _refus("une action à l'ouverture")

        # Parcours de tout le graphe d'objets atteignables depuis le trailer, y compris les objets rangés dans des
        # flux d'objets compressés. Chaque objet indirect n'est visité qu'une fois.
        # Les objets orphelins listés dans la table des références croisées sont analysés aussi.
        vus: set[tuple[int, int]] = set()
        pile: list = [lecteur.trailer]
        for generation, objets in lecteur.xref.items():
            pile.extend(IndirectObject(idnum, generation, lecteur) for idnum in objets)
        pile.extend(IndirectObject(idnum, 0, lecteur) for idnum in lecteur.xref_objStm)
        if len(pile) > OBJETS_MAX:
            return Verdict(False, MOTIF_TROP_LONG)
        visites = 0
        while pile:
            objet = pile.pop()
            if isinstance(objet, IndirectObject):
                cle = (objet.idnum, objet.generation)
                if cle in vus:
                    continue
                vus.add(cle)
                objet = objet.get_object()
            visites += 1
            if visites > OBJETS_MAX:
                return Verdict(False, MOTIF_TROP_LONG)
            if isinstance(objet, DictionaryObject):
                for nom in objet:
                    if nom in CLES_INTERDITES:
                        return _refus(CLES_INTERDITES[nom])
                for nom in ("/Type", "/Subtype"):
                    valeur = _cle(objet.get(nom))
                    if valeur in TYPES_INTERDITS:
                        return _refus(TYPES_INTERDITS[valeur])
                # Les actions se trouvent sous /A (liens, signets), /Next (enchaînement) ou portent /Type /Action.
                # /S seul ne suffit pas : il désigne aussi les éléments de structure, masques et transitions.
                actions = [objet.get(nom) for nom in ("/A", "/Next")]
                if _cle(objet.get("/Type")) == "/Action":
                    actions.append(objet)
                for action in actions:
                    if action is None:
                        continue
                    action = action.get_object()
                    suivantes = action if isinstance(action, ArrayObject) else [action]
                    for a in suivantes:
                        a = a.get_object()
                        if isinstance(a, DictionaryObject) and (refus := _verifier_action(a)) is not None:
                            return refus
                pile.extend(v for k, v in objet.items() if k != "/Parent")
            elif isinstance(objet, ArrayObject):
                pile.extend(objet)
    except MemoryError:
        return Verdict(False, MOTIF_TROP_LONG)
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, IndexError, OSError, RecursionError):
        return Verdict(False, MOTIF_ILLISIBLE)
    return Verdict(True)


def _limiter_ressources(memoire_mo: int, duree_s: int) -> None:
    try:
        import resource
    except ImportError:  # Windows : seule la durée maximale, surveillée par le processus parent, s'applique.
        return
    for limite, valeur in ((resource.RLIMIT_AS, memoire_mo * 1024 * 1024), (resource.RLIMIT_CPU, max(1, int(duree_s)))):
        try:
            resource.setrlimit(limite, (valeur, valeur))
        except (ValueError, OSError):
            pass


def _travailleur(contenu: bytes, envoi, memoire_mo: int, duree_s: int) -> None:
    """Point d'entrée du processus d'analyse (les limites sont passées en argument : rien n'est hérité)."""
    _limiter_ressources(memoire_mo, duree_s)
    try:
        envoi.send(analyser(contenu))
    except MemoryError:
        envoi.send(Verdict(False, MOTIF_TROP_LONG))
    finally:
        envoi.close()


_places = threading.BoundedSemaphore(ANALYSES_SIMULTANEES)


def analyser_isole(contenu: bytes) -> None:
    """Analyse dans un processus séparé et borné. Lève `PdfRefuse` si le PDF est refusé."""
    with _places:
        contexte = multiprocessing.get_context("spawn")
        reception, envoi = contexte.Pipe(duplex=False)
        processus = contexte.Process(
            target=_travailleur, args=(contenu, envoi, MEMOIRE_MAX_MO, DUREE_MAX_S), daemon=True
        )
        processus.start()
        envoi.close()
        try:
            verdict = reception.recv() if reception.poll(DUREE_MAX_S) else None
        except EOFError:  # processus mort (limite de mémoire ou de temps processeur atteinte)
            verdict = None
        finally:
            reception.close()
            processus.join(1)
            if processus.is_alive():
                processus.kill()
                processus.join()
    if verdict is None:
        raise PdfRefuse(MOTIF_TROP_LONG)
    if not verdict.accepte:
        raise PdfRefuse(verdict.motif)
