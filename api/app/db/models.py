"""Les tables de PKP Math Lycée (voir docs/ARCHITECTURE.md).

Règles portées par le schéma :
- un élève = prénom + classe, unique dans sa classe, sans autre donnée personnelle ;
- supprimer une classe ou un élève supprime ses séances et réponses (purge RGPD) ;
- une question n'est jamais supprimée : on l'archive (voir `SuppressionInterdite`).
"""

from datetime import UTC, date, datetime

from pkp_engine import Niveau, TypeQuestion
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    JSON,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    false,
    func,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.referentiel import (
    SOURCE_PKP,
    Adaptation,
    Parcours,
    PorteeRessource,
    PublicRessource,
    Role,
    StatutValidation,
    TypeRessource,
)

# Noms de contraintes explicites : indispensable pour des migrations Alembic stables.
CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENTION)


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _enum(enum_cls: type, nom: str) -> Enum:
    # Stocke la valeur (« 2nde », « qcm ») en VARCHAR + CHECK : portable SQLite/PostgreSQL.
    return Enum(
        enum_cls,
        name=nom,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


# Chapitres ouverts par l'enseignant pour une classe (il les ouvre au fil de l'année).
chapitres_de_classe = Table(
    "classe_chapitre",
    Base.metadata,
    Column("classe_id", ForeignKey("classe.id", ondelete="CASCADE"), primary_key=True),
    Column("chapitre_id", ForeignKey("chapitre.id", ondelete="RESTRICT"), primary_key=True),
)

# Chapitres choisis par l'élève au démarrage d'une séance (parmi ceux ouverts).
chapitres_de_seance = Table(
    "seance_chapitre",
    Base.metadata,
    Column("seance_id", ForeignKey("seance.id", ondelete="CASCADE"), primary_key=True),
    Column("chapitre_id", ForeignKey("chapitre.id", ondelete="RESTRICT"), primary_key=True),
)


class Enseignant(Base):
    __tablename__ = "enseignant"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    # Un administrateur est aussi enseignant : il change d'espace par le menu (cahier des charges V2, § 2).
    role: Mapped[Role] = mapped_column(_enum(Role, "role"), default=Role.ENSEIGNANT, server_default=Role.ENSEIGNANT.value)
    # Désactivé : ni lui ni ses élèves ne peuvent se connecter ; aucune donnée n'est supprimée.
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Mot de passe donné par un administrateur : à changer avant tout autre usage.
    mdp_provisoire: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Secret TOTP (RFC 6238) du second facteur, obligatoire pour l'espace administrateur en production.
    totp_secret: Mapped[str | None] = mapped_column(String(64))

    classes: Mapped[list["Classe"]] = relationship(back_populates="enseignant")


class Classe(Base):
    __tablename__ = "classe"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    niveau: Mapped[Niveau] = mapped_column(_enum(Niveau, "niveau"))
    # Spécialité suivie : seuls les chapitres de ce parcours sont proposés aux élèves.
    parcours: Mapped[Parcours] = mapped_column(_enum(Parcours, "parcours"), server_default=Parcours.SPECIALITE.value)
    enseignant_id: Mapped[int] = mapped_column(ForeignKey("enseignant.id", ondelete="RESTRICT"), index=True)

    enseignant: Mapped[Enseignant] = relationship(back_populates="classes")
    chapitres_proposes: Mapped[list["Chapitre"]] = relationship(secondary=chapitres_de_classe)
    eleves: Mapped[list["Eleve"]] = relationship(
        back_populates="classe", cascade="all, delete-orphan", passive_deletes=True
    )


class Eleve(Base):
    __tablename__ = "eleve"
    __table_args__ = (UniqueConstraint("prenom", "classe_id", name="uq_eleve_prenom_classe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    prenom: Mapped[str] = mapped_column(String(50))
    classe_id: Mapped[int] = mapped_column(ForeignKey("classe.id", ondelete="CASCADE"), index=True)
    # Point de départ de la durée de conservation pour un élève sans séance.
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    # Empreinte du code personnel distribué par l'enseignant (audit A-07, décision D1).
    # Vide tant que l'enseignant n'a pas généré de code : l'élève ne peut pas se connecter.
    code_hash: Mapped[str | None] = mapped_column(String(255))

    classe: Mapped[Classe] = relationship(back_populates="eleves")
    seances: Mapped[list["Seance"]] = relationship(
        back_populates="eleve", cascade="all, delete-orphan", passive_deletes=True
    )


class Chapitre(Base):
    __tablename__ = "chapitre"
    __table_args__ = (UniqueConstraint("niveau", "parcours", "ordre", name="uq_chapitre_niveau_parcours_ordre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifiant stable venant des fichiers contenu/*.yaml (import idempotent).
    code: Mapped[str] = mapped_column(String(40), unique=True)
    niveau: Mapped[Niveau] = mapped_column(_enum(Niveau, "niveau"))
    parcours: Mapped[Parcours] = mapped_column(_enum(Parcours, "parcours"), server_default=Parcours.SPECIALITE.value)
    titre: Mapped[str] = mapped_column(String(200))
    ordre: Mapped[int] = mapped_column(Integer)
    # Masqué par un administrateur : plus proposé aux classes, l'historique reste lisible.
    masque: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    competences: Mapped[list["Competence"]] = relationship(back_populates="chapitre")


class Competence(Base):
    __tablename__ = "competence"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapitre_id: Mapped[int] = mapped_column(ForeignKey("chapitre.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    libelle: Mapped[str] = mapped_column(String(200))
    ordre: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    masque: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    chapitre: Mapped[Chapitre] = relationship(back_populates="competences")
    questions: Mapped[list["Question"]] = relationship(back_populates="competence")
    lecon: Mapped["Lecon | None"] = relationship(back_populates="competence")


class Lecon(Base):
    """Cours et résumé d'une compétence, en Markdown avec formules LaTeX ($…$)."""

    __tablename__ = "lecon"

    id: Mapped[int] = mapped_column(primary_key=True)
    competence_id: Mapped[int] = mapped_column(ForeignKey("competence.id", ondelete="CASCADE"), unique=True)
    cours: Mapped[str] = mapped_column(Text)
    resume: Mapped[str] = mapped_column(Text)
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, onupdate=_maintenant)
    # Modifiée depuis l'IHM d'administration : l'import YAML ne l'écrase plus (décision DA2).
    modifiee_admin_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    competence: Mapped[Competence] = relationship(back_populates="lecon")
    versions: Mapped[list["LeconVersion"]] = relationship(
        back_populates="lecon", cascade="all, delete-orphan", passive_deletes=True, order_by="LeconVersion.id"
    )


class LeconVersion(Base):
    """État d'une leçon avant chaque modification depuis l'IHM : comparer et restaurer."""

    __tablename__ = "lecon_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    lecon_id: Mapped[int] = mapped_column(ForeignKey("lecon.id", ondelete="CASCADE"), index=True)
    cours: Mapped[str] = mapped_column(Text)
    resume: Mapped[str] = mapped_column(Text)
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

    lecon: Mapped[Lecon] = relationship(back_populates="versions")
    auteur: Mapped["Enseignant | None"] = relationship()


class Question(Base):
    __tablename__ = "question"
    __table_args__ = (CheckConstraint("difficulte BETWEEN 1 AND 5", name="difficulte_1_a_5"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifiant stable pour les questions importées depuis contenu/*.yaml ;
    # vide pour les questions créées depuis l'interface enseignant.
    code: Mapped[str | None] = mapped_column(String(60), unique=True)
    competence_id: Mapped[int] = mapped_column(ForeignKey("competence.id", ondelete="RESTRICT"), index=True)
    enonce: Mapped[str] = mapped_column(Text)
    type: Mapped[TypeQuestion] = mapped_column(_enum(TypeQuestion, "type_question"))
    solution: Mapped[str] = mapped_column(String(200))
    difficulte: Mapped[int] = mapped_column(Integer)
    archivee: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Registre des sources : d'où vient la question et à quelles conditions on peut l'utiliser.
    source: Mapped[str] = mapped_column(String(200), default=SOURCE_PKP, server_default=SOURCE_PKP)
    source_url: Mapped[str | None] = mapped_column(String(500))
    licence_source: Mapped[str | None] = mapped_column(String(100))
    adaptation: Mapped[Adaptation] = mapped_column(
        _enum(Adaptation, "adaptation"), default=Adaptation.ORIGINALE, server_default=Adaptation.ORIGINALE.value
    )
    # Validation pédagogique par un enseignant (statut, auteur, date).
    statut_validation: Mapped[StatutValidation] = mapped_column(
        _enum(StatutValidation, "statut_validation"),
        default=StatutValidation.A_VALIDER,
        server_default=StatutValidation.A_VALIDER.value,
    )
    valide_par: Mapped[str | None] = mapped_column(String(100))
    valide_le: Mapped[date | None] = mapped_column(Date)
    # Auteur de la question : le relecteur doit être une autre personne.
    auteur: Mapped[str | None] = mapped_column(String(100))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)
    modifiee_admin_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    competence: Mapped[Competence] = relationship(back_populates="questions")


class Seance(Base):
    __tablename__ = "seance"

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Question servie et pas encore répondue : l'élève ne peut répondre qu'à elle,
    # et la durée de réponse est mesurée côté serveur.
    question_courante_id: Mapped[int | None] = mapped_column(ForeignKey("question.id", ondelete="RESTRICT"))
    question_servie_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    eleve: Mapped[Eleve] = relationship(back_populates="seances")
    question_courante: Mapped["Question | None"] = relationship()
    # Vide pour les séances antérieures à ce choix : tous les chapitres ouverts de la classe.
    chapitres: Mapped[list["Chapitre"]] = relationship(secondary=chapitres_de_seance)
    reponses: Mapped[list["Reponse"]] = relationship(
        back_populates="seance", cascade="all, delete-orphan", passive_deletes=True
    )


class Reponse(Base):
    __tablename__ = "reponse"

    id: Mapped[int] = mapped_column(primary_key=True)
    seance_id: Mapped[int] = mapped_column(ForeignKey("seance.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="RESTRICT"), index=True)
    reponse_donnee: Mapped[str] = mapped_column(String(200))
    correcte: Mapped[bool] = mapped_column(Boolean)
    duree_s: Mapped[float] = mapped_column(Float)
    repondu_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

    seance: Mapped[Seance] = relationship(back_populates="reponses")
    question: Mapped[Question] = relationship()


class JournalAdmin(Base):
    """Toute écriture d'un administrateur : qui, quoi, sur quel objet, avant et après."""

    __tablename__ = "journal_admin"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(60))
    objet: Mapped[str] = mapped_column(String(40))
    objet_id: Mapped[int | None] = mapped_column(Integer)
    avant: Mapped[dict | None] = mapped_column(JSON)
    apres: Mapped[dict | None] = mapped_column(JSON)
    le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)

    admin: Mapped["Enseignant | None"] = relationship()


# Classes auxquelles un professeur destine une ressource de portée « classe ».
ressources_de_classe = Table(
    "ressource_classe",
    Base.metadata,
    Column("ressource_id", ForeignKey("ressource.id", ondelete="CASCADE"), primary_key=True),
    Column("classe_id", ForeignKey("classe.id", ondelete="CASCADE"), primary_key=True),
)


class Ressource(Base):
    """Lien vers un site ou fichier PDF, rattaché à un chapitre ou à une compétence."""

    __tablename__ = "ressource"
    __table_args__ = (
        CheckConstraint("(chapitre_id IS NULL) <> (competence_id IS NULL)", name="un_seul_rattachement"),
        CheckConstraint("(type = 'lien') = (url IS NOT NULL)", name="url_si_lien"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[TypeRessource] = mapped_column(_enum(TypeRessource, "type_ressource"))
    titre: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(300), default="", server_default="")
    url: Mapped[str | None] = mapped_column(String(500))
    domaine: Mapped[str | None] = mapped_column(String(253))
    # PDF : nom aléatoire dans le dossier des fichiers, jamais le nom envoyé par l'utilisateur.
    fichier: Mapped[str | None] = mapped_column(String(64), unique=True)
    taille_octets: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(200))
    licence: Mapped[str | None] = mapped_column(String(100))
    chapitre_id: Mapped[int | None] = mapped_column(ForeignKey("chapitre.id", ondelete="CASCADE"), index=True)
    competence_id: Mapped[int | None] = mapped_column(ForeignKey("competence.id", ondelete="CASCADE"), index=True)
    portee: Mapped[PorteeRessource] = mapped_column(_enum(PorteeRessource, "portee_ressource"))
    public: Mapped[PublicRessource] = mapped_column(
        _enum(PublicRessource, "public_ressource"), default=PublicRessource.TOUS, server_default=PublicRessource.TOUS.value
    )
    auteur_id: Mapped[int] = mapped_column(ForeignKey("enseignant.id", ondelete="CASCADE"), index=True)
    masquee: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    motif_masquage: Mapped[str | None] = mapped_column(String(300))
    # Contrôle hebdomadaire des liens : nombre d'échecs consécutifs (masqué aux élèves à partir de 2).
    echecs_lien: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    lien_verifie_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ordre: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

    chapitre: Mapped["Chapitre | None"] = relationship()
    competence: Mapped["Competence | None"] = relationship()
    auteur: Mapped[Enseignant] = relationship()
    classes: Mapped[list[Classe]] = relationship(secondary=ressources_de_classe)


class RessourceConsultation(Base):
    """Compteur d'ouvertures par jour, sans identifier qui a ouvert."""

    __tablename__ = "ressource_consultation"

    ressource_id: Mapped[int] = mapped_column(ForeignKey("ressource.id", ondelete="CASCADE"), primary_key=True)
    jour: Mapped[date] = mapped_column(Date, primary_key=True)
    nombre: Mapped[int] = mapped_column(Integer, default=0)


class DomaineInterdit(Base):
    """Domaines refusés pour les liens (les élèves sont mineurs)."""

    __tablename__ = "domaine_interdit"

    id: Mapped[int] = mapped_column(primary_key=True)
    domaine: Mapped[str] = mapped_column(String(253), unique=True)


class SuppressionInterdite(RuntimeError):
    """Une question ne se supprime pas : mettre `archivee = True`."""


@event.listens_for(Session, "before_flush")
def _interdire_suppression_question(session: Session, _contexte, _instances) -> None:
    # Filet côté ORM ; côté base, la clé étrangère RESTRICT protège déjà
    # toute question ayant reçu au moins une réponse.
    if any(isinstance(objet, Question) for objet in session.deleted):
        raise SuppressionInterdite("Une question ne se supprime pas : archivez-la (archivee = True).")
