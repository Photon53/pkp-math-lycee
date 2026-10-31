"""Matrice de couverture d'un programme officiel par le contenu PKP, et rapport des écarts.

Générée, jamais écrite à la main : elle ne peut pas diverger du contenu ni des référentiels.

Statut d'un attendu (du plus faible au plus fort) :
- absent : aucune compétence ne le déclare ;
- partiel : déclaré, mais pas encore enseigné (cours ou méthode) et évalué ;
- enseigné, évaluation non automatisée : démonstration ou rédaction, que le moteur ne corrige pas ;
- évalué : enseigné, et au moins SEUIL_QUESTIONS questions actives sur au moins SEUIL_DIFFICULTES difficultés ;
- validé : évalué, et au moins SEUIL_QUESTIONS de ces questions validées par un relecteur.
"""

from dataclasses import dataclass, field
from datetime import date

from app.contenu import FichierContenu
from app.programmes import Attendu, ModeEvaluation, Referentiels, Theme
from app.referentiel import StatutValidation

SEUIL_QUESTIONS = 5
SEUIL_DIFFICULTES = 3

ABSENT, PARTIEL, NON_AUTOMATISE, EVALUE, VALIDE = (
    "absent", "partiel", "enseigné, évaluation non automatisée", "évalué", "validé",
)
SYMBOLES = {ABSENT: "✗", PARTIEL: "◐", NON_AUTOMATISE: "✎", EVALUE: "●", VALIDE: "✓"}


@dataclass
class Ligne:
    theme: Theme
    attendu: Attendu
    competences: list[str] = field(default_factory=list)
    enseigne: bool = False
    questions: int = 0
    validees: int = 0
    corrigees: int = 0
    difficultes: set[int] = field(default_factory=set)

    @property
    def statut(self) -> str:
        if not self.competences:
            return ABSENT
        if self.attendu.evaluation is not ModeEvaluation.AUTOMATIQUE:
            return NON_AUTOMATISE if self.enseigne else PARTIEL
        if not self.enseigne or self.questions < SEUIL_QUESTIONS or len(self.difficultes) < SEUIL_DIFFICULTES:
            return PARTIEL
        return VALIDE if self.validees >= SEUIL_QUESTIONS else EVALUE


def couverture(referentiels: Referentiels, fichiers: list[tuple[object, FichierContenu]], programme: str) -> list[Ligne]:
    lignes = {a.code: Ligne(t, a) for t, a in referentiels.du_programme(programme)}
    for _, contenu in fichiers:
        for c in contenu.competences:
            for code in c.attendus:
                ligne = lignes.get(code)
                if ligne is None:
                    continue
                ligne.competences.append(c.code)
                ligne.enseigne |= c.cours is not None or bool(c.methodes)
                for q in c.questions:
                    if q.archivee:
                        continue
                    ligne.questions += 1
                    ligne.validees += q.validation.statut is StatutValidation.VALIDEE
                    ligne.corrigees += q.correction is not None
                    ligne.difficultes.add(q.difficulte)
    return list(lignes.values())


def competences_non_rattachees(referentiels: Referentiels, fichiers, programme: str) -> list[str]:
    """Compétences du niveau et du parcours du programme qui ne déclarent aucun de ses attendus."""
    p = referentiels.programmes[programme]
    codes = {a.code for _, a in referentiels.du_programme(programme)}
    return [
        f"{c.code} ({contenu.chapitre.titre})"
        for _, contenu in fichiers
        if contenu.chapitre.niveau == p.niveau and contenu.chapitre.parcours == p.parcours
        for c in contenu.competences
        if not codes.intersection(c.attendus)
    ]


def _pourcentage(n: int, total: int) -> str:
    return f"{round(100 * n / total)} %" if total else "—"


def en_markdown(referentiels: Referentiels, fichiers, programme: str, jour: date) -> str:
    p = referentiels.programmes[programme]
    source = referentiels.sources[p.source]
    lignes = couverture(referentiels, fichiers, programme)
    obligatoires = [l for l in lignes if l.attendu.obligatoire]
    compte = {s: sum(l.statut == s for l in obligatoires) for s in SYMBOLES}
    sortie = [
        f"# Matrice de couverture — {p.titre}",
        "",
        f"Fichier **généré** par `python -m app.contenu matrice` le {jour.isoformat()} : ne pas modifier à la main.",
        f"Source : {source.titre}, {source.bulletin} (`referentiels/sources/{source.fichier}`).",
        "",
        f"- Attendus saisis : **{len(lignes)}**, dont {len(obligatoires)} obligatoires "
        f"(les approfondissements ne le sont pas).",
        f"- Obligatoires évalués ou validés : **{_pourcentage(compte[EVALUE] + compte[VALIDE], len(obligatoires))}** · "
        f"validés : {_pourcentage(compte[VALIDE], len(obligatoires))} · absents : {compte[ABSENT]}.",
        f"- Légende : {' · '.join(f'{s} {nom}' for nom, s in SYMBOLES.items())}. "
        f"« Évalué » = cours ou méthode, au moins {SEUIL_QUESTIONS} questions sur {SEUIL_DIFFICULTES} difficultés.",
        "",
        "La couverture ne porte que sur les thèmes déjà saisis dans `referentiels/` : un thème non saisi n'apparait pas.",
        "",
    ]
    for theme in dict.fromkeys(l.theme.code for l in lignes):
        du_theme = [l for l in lignes if l.theme.code == theme]
        sortie += [
            f"## {du_theme[0].theme.titre} ({du_theme[0].theme.partie})",
            "",
            "| | Attendu | Type | Compétences PKP | Questions (validées) | Difficultés | Corrigées |",
            "|:-:|---|---|---|:-:|:-:|:-:|",
        ]
        for l in du_theme:
            texte = l.attendu.texte.replace("|", "\\|")
            sortie.append(
                f"| {SYMBOLES[l.statut]} | `{l.attendu.code}` {texte} | {l.attendu.type.value} | "
                f"{', '.join(f'`{c}`' for c in l.competences) or '—'} | {l.questions} ({l.validees}) | "
                f"{''.join(map(str, sorted(l.difficultes))) or '—'} | {l.corrigees} |"
            )
        sortie.append("")
    non_rattachees = competences_non_rattachees(referentiels, fichiers, programme)
    if non_rattachees:
        sortie += [
            "## Compétences PKP non rattachées à ce programme",
            "",
            "Hors programme, ou rattachement à faire (champ `attendus` du fichier de contenu) :",
            "",
            *[f"- `{c}`" for c in non_rattachees],
            "",
        ]
    return "\n".join(sortie)


def ecarts(referentiels: Referentiels, fichiers, programme: str) -> str:
    lignes = couverture(referentiels, fichiers, programme)
    sortie = [f"Écarts au programme {programme} :"]
    for statut in (ABSENT, PARTIEL, NON_AUTOMATISE, EVALUE):
        concernes = [l for l in lignes if l.statut == statut and l.attendu.obligatoire]
        if concernes:
            sortie.append(f"\n{SYMBOLES[statut]} {statut} ({len(concernes)}) :")
            for l in concernes:
                detail = f"{l.questions} question(s), {l.validees} validée(s)" if l.competences else "à créer"
                sortie.append(f"  - {l.attendu.code} [{l.attendu.type.value}] {l.attendu.texte[:90]} — {detail}")
    facultatifs = [l for l in lignes if not l.attendu.obligatoire and l.statut == ABSENT]
    if facultatifs:
        sortie.append(f"\nApprofondissements non traités (facultatifs) : {', '.join(l.attendu.code for l in facultatifs)}")
    non_rattachees = competences_non_rattachees(referentiels, fichiers, programme)
    if non_rattachees:
        sortie.append(f"\nCompétences non rattachées : {', '.join(non_rattachees)}")
    if len(sortie) == 1:
        sortie.append("aucun : tous les attendus obligatoires saisis sont validés.")
    return "\n".join(sortie)
