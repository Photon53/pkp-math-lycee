"""Les 8 tables de PKP Math Lycée (voir docs/ARCHITECTURE.md).

Règles portées par le schéma :
- un élève = prénom + classe, unique dans sa classe, sans autre donnée personnelle ;
- supprimer une classe ou un élève supprime ses séances et réponses (purge RGPD) ;
- une question n'est jamais supprimée : on l'archive (voir `SuppressionInterdite`).
"""

from datetime import UTC, datetime

from pkp_engine import Niveau, TypeQuestion
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    event,
    false,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

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


class Enseignant(Base):
    __tablename__ = "enseignant"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))

    classes: Mapped[list["Classe"]] = relationship(back_populates="enseignant")


class Classe(Base):
    __tablename__ = "classe"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    niveau: Mapped[Niveau] = mapped_column(_enum(Niveau, "niveau"))
    enseignant_id: Mapped[int] = mapped_column(ForeignKey("enseignant.id", ondelete="RESTRICT"), index=True)

    enseignant: Mapped[Enseignant] = relationship(back_populates="classes")
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

    classe: Mapped[Classe] = relationship(back_populates="eleves")
    seances: Mapped[list["Seance"]] = relationship(
        back_populates="eleve", cascade="all, delete-orphan", passive_deletes=True
    )


class Chapitre(Base):
    __tablename__ = "chapitre"
    __table_args__ = (UniqueConstraint("niveau", "ordre", name="uq_chapitre_niveau_ordre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    niveau: Mapped[Niveau] = mapped_column(_enum(Niveau, "niveau"))
    titre: Mapped[str] = mapped_column(String(200))
    ordre: Mapped[int] = mapped_column(Integer)

    competences: Mapped[list["Competence"]] = relationship(back_populates="chapitre")


class Competence(Base):
    __tablename__ = "competence"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapitre_id: Mapped[int] = mapped_column(ForeignKey("chapitre.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    libelle: Mapped[str] = mapped_column(String(200))

    chapitre: Mapped[Chapitre] = relationship(back_populates="competences")
    questions: Mapped[list["Question"]] = relationship(back_populates="competence")


class Question(Base):
    __tablename__ = "question"
    __table_args__ = (CheckConstraint("difficulte BETWEEN 1 AND 5", name="difficulte_1_a_5"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competence_id: Mapped[int] = mapped_column(ForeignKey("competence.id", ondelete="RESTRICT"), index=True)
    enonce: Mapped[str] = mapped_column(Text)
    type: Mapped[TypeQuestion] = mapped_column(_enum(TypeQuestion, "type_question"))
    solution: Mapped[str] = mapped_column(String(200))
    difficulte: Mapped[int] = mapped_column(Integer)
    archivee: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

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


class SuppressionInterdite(RuntimeError):
    """Une question ne se supprime pas : mettre `archivee = True`."""


@event.listens_for(Session, "before_flush")
def _interdire_suppression_question(session: Session, _contexte, _instances) -> None:
    # Filet côté ORM ; côté base, la clé étrangère RESTRICT protège déjà
    # toute question ayant reçu au moins une réponse.
    if any(isinstance(objet, Question) for objet in session.deleted):
        raise SuppressionInterdite("Une question ne se supprime pas : archivez-la (archivee = True).")
