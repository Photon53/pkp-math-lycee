"""Les tables de PKP Math Lycée (voir docs/ARCHITECTURE.md).

Règles portées par le schéma :
- un élève = prénom + classe, unique dans sa classe, sans autre donnée personnelle ;
- supprimer une classe ou un élève supprime ses séances et réponses (purge RGPD) ;
- une question n'est jamais supprimée : on l'archive (voir `SuppressionInterdite`).
"""

from datetime import UTC, date, datetime

from pkp_engine import Forme, Niveau, TypeQuestion
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

# Séance ciblée sur des compétences (bouton « S'entraîner » d'une leçon) ; vide = tous les chapitres choisis.
competences_de_seance = Table(
    "seance_competence",
    Base.metadata,
    Column("seance_id", ForeignKey("seance.id", ondelete="CASCADE"), primary_key=True),
    Column("competence_id", ForeignKey("competence.id", ondelete="RESTRICT"), primary_key=True),
)

# Comptes parents : chaque parent suit un ou plusieurs enfants (inscriptions élève).
enfants_de_parent = Table(
    "parent_eleve",
    Base.metadata,
    Column("parent_id", ForeignKey("parent.id", ondelete="CASCADE"), primary_key=True),
    Column("eleve_id", ForeignKey("eleve.id", ondelete="CASCADE"), primary_key=True, index=True),
)

# Familles créées par l'administrateur : chaque parent a un ou plusieurs enfants (personnes, pas inscriptions).
enfants_de_famille = Table(
    "parent_enfant",
    Base.metadata,
    Column("parent_id", ForeignKey("parent.id", ondelete="CASCADE"), primary_key=True),
    Column("enfant_id", ForeignKey("enfant.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Enseignant(Base):
    __tablename__ = "enseignant"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    # Un administrateur est aussi enseignant : il change d'espace par le menu (cahier des charges V2, § 2).
    role: Mapped[Role] = mapped_column(_enum(Role, "role"), default=Role.ENSEIGNANT, server_default=Role.ENSEIGNANT.value)
    # Disciplines cochées par un administrateur : chacune ouvre son espace (maths : /enseignant, anglais : /anglais).
    enseigne_maths: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    enseigne_anglais: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Désactivé : ni lui ni ses élèves ne peuvent se connecter ; aucune donnée n'est supprimée.
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Mot de passe donné par un administrateur : à changer avant tout autre usage.
    mdp_provisoire: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Secret TOTP (RFC 6238) du second facteur, obligatoire pour l'espace administrateur en production.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    # Coché par un administrateur : valide les séances PKP Anglais (jamais les siennes).
    referent_anglais: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    classes: Mapped[list["Classe"]] = relationship(back_populates="enseignant")
    groupes_anglais: Mapped[list["GroupeAnglais"]] = relationship(back_populates="enseignant")
    # Domaines où il enseigne et où il valide ; les cases ci-dessus en sont déduites (`app.permissions`).
    habilitations: Mapped[list["Habilitation"]] = relationship(
        foreign_keys="Habilitation.enseignant_id", back_populates="enseignant",
        cascade="all, delete-orphan", passive_deletes=True, order_by="Habilitation.id",
    )


class Classe(Base):
    __tablename__ = "classe"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    niveau: Mapped[Niveau] = mapped_column(_enum(Niveau, "niveau"))
    # Spécialité suivie : seuls les chapitres de ce parcours sont proposés aux élèves.
    parcours: Mapped[Parcours] = mapped_column(_enum(Parcours, "parcours"), server_default=Parcours.SPECIALITE.value)
    enseignant_id: Mapped[int] = mapped_column(ForeignKey("enseignant.id", ondelete="RESTRICT"), index=True)
    # Domaine pédagogique (CDC V2, EX.2) : filtre de l'admin, ouverture au public, droits de validation.
    domaine_code: Mapped[str] = mapped_column(
        ForeignKey("domaine_pedagogique.code", ondelete="RESTRICT"), index=True, default="maths-lycee", server_default="maths-lycee"
    )
    # Archivage (V3, Lot 3) : hors des listes actives, plus de séance ; inscriptions et travail conservés.
    archivee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archivee_par: Mapped[str | None] = mapped_column(String(80))
    motif_archivage: Mapped[str | None] = mapped_column(String(200))

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
    # Identifiant de connexion (« ines-k7m4 ») : avec le code personnel, il suffit pour se connecter,
    # sans prénom ni code classe à saisir. Attribué avec le code personnel.
    identifiant: Mapped[str | None] = mapped_column(String(40), unique=True)
    # Même élève inscrit dans plusieurs classes (spécialité, mise à niveau, excellence…) : ses inscriptions
    # partagent ce numéro (l'id de la première), et il passe de l'une à l'autre sans ressaisir de code.
    groupe_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # Enfant d'une famille (créé par l'administrateur) : il se connecte avec la carte de l'enfant, et cette
    # inscription partage son code. Vide pour les élèves créés directement dans une classe (ancien mode).
    enfant_id: Mapped[int | None] = mapped_column(ForeignKey("enfant.id", ondelete="CASCADE"), index=True)

    classe: Mapped[Classe] = relationship(back_populates="eleves")
    enfant: Mapped["Enfant | None"] = relationship(back_populates="inscriptions")
    seances: Mapped[list["Seance"]] = relationship(
        back_populates="eleve", cascade="all, delete-orphan", passive_deletes=True
    )
    parents: Mapped[list["Parent"]] = relationship(
        secondary=enfants_de_parent, back_populates="enfants", passive_deletes=True
    )


class Parent(Base):
    """Compte parent, créé par le professeur d'un de ses enfants (e-mail + mot de passe provisoire).

    Le parent suit le travail de ses enfants et choisit leur code personnel. Sans enfant rattaché,
    le compte n'a plus de raison d'être : il est supprimé (voir `app.parents.supprimer_orphelins`).
    """

    __tablename__ = "parent"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    # Nom et prénom du responsable légal (V3, Lot 1) : facultatifs, vides pour les comptes existants.
    nom: Mapped[str] = mapped_column(String(50), default="", server_default="")
    prenom: Mapped[str] = mapped_column(String(50), default="", server_default="")
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    # Donné par le professeur ou un administrateur : à changer avant tout autre usage.
    mdp_provisoire: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Compte suspendu temporairement par l'administrateur (rien n'est effacé).
    bloque_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    enfants: Mapped[list[Eleve]] = relationship(secondary=enfants_de_parent, back_populates="parents")
    famille: Mapped[list["Enfant"]] = relationship(secondary=enfants_de_famille, back_populates="parents")


class Enfant(Base):
    """Un enfant d'une famille : une personne, avec son niveau d'études et une seule carte de connexion.

    Il est inscrit ensuite dans des classes de maths (une inscription `Eleve` par parcours) et des groupes
    d'anglais (`EleveAnglais`) ; toutes ces inscriptions partagent son code personnel.
    """

    __tablename__ = "enfant"

    id: Mapped[int] = mapped_column(primary_key=True)
    prenom: Mapped[str] = mapped_column(String(50))
    # Initiale ou nom de famille, facultatif : distingue deux enfants de même prénom dans une classe.
    nom: Mapped[str] = mapped_column(String(50), default="", server_default="")
    niveau: Mapped[Niveau] = mapped_column(_enum(Niveau, "niveau"))
    identifiant: Mapped[str] = mapped_column(String(40), unique=True)
    code_hash: Mapped[str | None] = mapped_column(String(255))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Carte suspendue temporairement par l'administrateur, dans toutes les matières.
    bloque_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parents: Mapped[list[Parent]] = relationship(secondary=enfants_de_famille, back_populates="famille")
    inscriptions: Mapped[list[Eleve]] = relationship(
        back_populates="enfant", cascade="all, delete-orphan", passive_deletes=True
    )
    inscriptions_anglais: Mapped[list["EleveAnglais"]] = relationship(
        back_populates="enfant", cascade="all, delete-orphan", passive_deletes=True
    )


# Ordre d'affichage des niveaux d'anglais ; ceux qui sont ouverts sont les niveaux du domaine (EX.2).
NIVEAUX_ANGLAIS = ("6e", "5e", "4e", "3e", "2nde", "1re", "Tle")


class GroupeAnglais(Base):
    """Groupe PKP Anglais (collège) : séparé des classes de maths, sans parcours ni chapitres (CDC anglais V1.8)."""

    __tablename__ = "groupe_anglais"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(60))
    niveau: Mapped[str] = mapped_column(String(4))
    enseignant_id: Mapped[int] = mapped_column(ForeignKey("enseignant.id", ondelete="RESTRICT"), index=True)
    # Domaine pédagogique (CDC V2, EX.2) : filtre de l'admin, ouverture au public, droits de validation.
    domaine_code: Mapped[str] = mapped_column(
        ForeignKey("domaine_pedagogique.code", ondelete="RESTRICT"), index=True, default="anglais-college", server_default="anglais-college"
    )
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    # Archivage (V3, Lot 3) : hors des listes actives, plus de séance ; inscriptions et travail conservés.
    archivee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archivee_par: Mapped[str | None] = mapped_column(String(80))
    motif_archivage: Mapped[str | None] = mapped_column(String(200))

    enseignant: Mapped[Enseignant] = relationship(back_populates="groupes_anglais")
    eleves: Mapped[list["EleveAnglais"]] = relationship(
        back_populates="groupe", cascade="all, delete-orphan", passive_deletes=True
    )


class EleveAnglais(Base):
    """Élève d'un groupe d'anglais : un prénom, rien d'autre."""

    __tablename__ = "eleve_anglais"
    __table_args__ = (UniqueConstraint("prenom", "groupe_id", name="uq_eleve_anglais_prenom_groupe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    prenom: Mapped[str] = mapped_column(String(50))
    groupe_id: Mapped[int] = mapped_column(ForeignKey("groupe_anglais.id", ondelete="CASCADE"), index=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    # Identifiant (« lina-k7m4 ») et empreinte du code personnel, attribués par le professeur :
    # même mécanisme que les élèves de maths. Régénérer le code déconnecte l'élève.
    identifiant: Mapped[str | None] = mapped_column(String(40), unique=True)
    code_hash: Mapped[str | None] = mapped_column(String(255))
    # Enfant d'une famille : même rôle que `Eleve.enfant_id`.
    enfant_id: Mapped[int | None] = mapped_column(ForeignKey("enfant.id", ondelete="CASCADE"), index=True)

    groupe: Mapped[GroupeAnglais] = relationship(back_populates="eleves")
    enfant: Mapped["Enfant | None"] = relationship(back_populates="inscriptions_anglais")
    progression: Mapped[list["ProgressionAnglais"]] = relationship(
        back_populates="eleve", cascade="all, delete-orphan", passive_deletes=True
    )


STATUTS_SEANCE_ANGLAIS = ("brouillon", "soumis", "valide", "refuse", "archive")


class SeanceAnglais(Base):
    """Séance PKP Anglais : son contenu vit dans ses versions (CDC anglais V1.8, validation).

    Version courante = la dernière ; version publiée = la dernière validée, seule ouverte aux élèves.
    """

    __tablename__ = "seance_anglais"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    niveau: Mapped[str] = mapped_column(String(4))
    # Domaine pédagogique (CDC V2, EX.2) : filtre de l'admin, ouverture au public, droits de validation.
    domaine_code: Mapped[str] = mapped_column(
        ForeignKey("domaine_pedagogique.code", ondelete="RESTRICT"), index=True, default="anglais-college", server_default="anglais-college"
    )

    versions: Mapped[list["SeanceAnglaisVersion"]] = relationship(
        back_populates="seance", cascade="all, delete-orphan", passive_deletes=True,
        order_by="SeanceAnglaisVersion.numero",
    )

    @property
    def courante(self) -> "SeanceAnglaisVersion":
        return self.versions[-1]

    @property
    def publiee(self) -> "SeanceAnglaisVersion | None":
        return next((v for v in reversed(self.versions) if v.statut == "valide"), None)


class SeanceAnglaisVersion(Base):
    """Une version d'une séance : déroulé, cahier et quiz, avec son circuit de validation."""

    __tablename__ = "seance_anglais_version"
    __table_args__ = (
        UniqueConstraint("seance_id", "numero", name="uq_seance_anglais_version_numero"),
        CheckConstraint(
            "statut IN ('brouillon', 'soumis', 'valide', 'refuse', 'archive')", name="ck_seance_anglais_version_statut"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    seance_id: Mapped[int] = mapped_column(ForeignKey("seance_anglais.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    # Fichier de séance (étapes, fiches A/B/C, corrigés), cahier de l'élève et QCM de grammaire.
    contenu: Mapped[dict] = mapped_column(JSON)
    cahier: Mapped[dict] = mapped_column(JSON)
    quiz: Mapped[list] = mapped_column(JSON)
    statut: Mapped[str] = mapped_column(String(10), default="brouillon")
    # Auteur vide = contenu importé du dépôt : tout référent peut alors le valider.
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    validateur_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    decide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motif_refus: Mapped[str | None] = mapped_column(Text)

    seance: Mapped[SeanceAnglais] = relationship(back_populates="versions")
    auteur: Mapped["Enseignant | None"] = relationship(foreign_keys=[auteur_id])
    validateur: Mapped["Enseignant | None"] = relationship(foreign_keys=[validateur_id])


class ProgressionAnglais(Base):
    """Résultat d'un élève sur une séance : meilleur score au quiz et auto-évaluation « I can »."""

    __tablename__ = "progression_anglais"
    __table_args__ = (UniqueConstraint("eleve_id", "code", name="uq_progression_anglais_eleve_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve_anglais.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(10))
    meilleur_score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    tentatives: Mapped[int] = mapped_column(Integer, default=0)
    # Un niveau par phrase « I can » : non_observe, avec_aide, en_cours, autonome.
    i_can: Mapped[list] = mapped_column(JSON, default=list)
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, onupdate=_maintenant)

    eleve: Mapped[EleveAnglais] = relationship(back_populates="progression")


class Chapitre(Base):
    __tablename__ = "chapitre"
    __table_args__ = (UniqueConstraint("domaine_code", "niveau", "parcours", "ordre", name="uq_chapitre_domaine_niveau_parcours_ordre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifiant stable venant des fichiers contenu/*.yaml (import idempotent).
    code: Mapped[str] = mapped_column(String(40), unique=True)
    niveau: Mapped[Niveau] = mapped_column(_enum(Niveau, "niveau"))
    parcours: Mapped[Parcours] = mapped_column(_enum(Parcours, "parcours"), server_default=Parcours.SPECIALITE.value)
    titre: Mapped[str] = mapped_column(String(200))
    ordre: Mapped[int] = mapped_column(Integer)
    # Masqué par un administrateur : plus proposé aux classes, l'historique reste lisible.
    masque: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Domaine pédagogique (CDC V2, EX.2) : filtre de l'admin, ouverture au public, droits de validation.
    domaine_code: Mapped[str] = mapped_column(
        ForeignKey("domaine_pedagogique.code", ondelete="RESTRICT"), index=True, default="maths-lycee", server_default="maths-lycee"
    )

    competences: Mapped[list["Competence"]] = relationship(back_populates="chapitre")


class Competence(Base):
    __tablename__ = "competence"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapitre_id: Mapped[int] = mapped_column(ForeignKey("chapitre.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    libelle: Mapped[str] = mapped_column(String(200))
    ordre: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    masque: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Contenu pédagogique structuré, importé de contenu/*.yaml (voir docs/CONTENU.md) ; vide = non renseigné.
    attendus: Mapped[list | None] = mapped_column(JSON)  # codes des attendus officiels couverts
    objectifs: Mapped[list | None] = mapped_column(JSON)
    prerequis: Mapped[list | None] = mapped_column(JSON)  # codes d'autres compétences
    methodes: Mapped[list | None] = mapped_column(JSON)  # [{titre, quand, etapes, exemple}]
    erreurs_frequentes: Mapped[list | None] = mapped_column(JSON)  # [{erreur, explication}]

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
    # Forme d'écriture exigée (« Développer », « Factoriser »…) ; vide : seule la valeur compte.
    forme: Mapped[Forme | None] = mapped_column(_enum(Forme, "forme"))
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
    # Correction détaillée {methode, etapes, resultat, erreurs_frequentes}, montrée après la réponse (E0.3).
    correction: Mapped[dict | None] = mapped_column(JSON)
    competences_secondaires: Mapped[list | None] = mapped_column(JSON)
    # Valeurs variables {parametres, calculs, conditions} : énoncé, solution et correction citent [[…]].
    gabarit: Mapped[dict | None] = mapped_column(JSON)
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
    # Valeurs tirées pour la question courante, si elle est à valeurs variables.
    tirage_courant: Mapped[dict | None] = mapped_column(JSON)

    eleve: Mapped[Eleve] = relationship(back_populates="seances")
    question_courante: Mapped["Question | None"] = relationship()
    # Vide pour les séances antérieures à ce choix : tous les chapitres ouverts de la classe.
    chapitres: Mapped[list["Chapitre"]] = relationship(secondary=chapitres_de_seance)
    competences: Mapped[list["Competence"]] = relationship(secondary=competences_de_seance)
    # Méthode PKP : « Je m'entraîne » (niveaux 1 à 3) ou « Je me dépasse » (niveaux 4 et 5) ; vide = tous.
    difficulte_min: Mapped[int | None] = mapped_column(Integer)
    difficulte_max: Mapped[int | None] = mapped_column(Integer)
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
    # Valeurs de l'exercice tel qu'il a été posé (question à valeurs variables) : l'historique le remontre.
    tirage: Mapped[dict | None] = mapped_column(JSON)

    seance: Mapped[Seance] = relationship(back_populates="reponses")
    question: Mapped[Question] = relationship()


class Remarque(Base):
    """Remarque ou suggestion d'un élève, d'un parent ou d'un professeur (ticket #30).

    Anonyme : aucune identité n'est enregistrée (ni nom, ni rôle, ni identifiant de compte) ; l'auteur suit sa
    remarque avec la référence et le code de suivi confidentiel (seule son empreinte est conservée).
    Avec son nom : rôle, identifiant et nom affiché de l'auteur, visibles des administrateurs qui la traitent.
    """

    __tablename__ = "remarque"
    __table_args__ = (
        CheckConstraint(
            "categorie IN ('bug', 'dysfonctionnement', 'amelioration-fonctionnelle', 'amelioration-pedagogique', "
            "'erreur-pedagogique', 'lien-inaccessible', 'question', 'autre')",
            name="categorie",
        ),
        CheckConstraint("statut IN ('recue', 'en-cours', 'resolue', 'fermee')", name="statut"),
        CheckConstraint("priorite IN ('basse', 'normale', 'haute')", name="priorite"),
        CheckConstraint("NOT anonyme OR (auteur_role IS NULL AND auteur_id IS NULL AND auteur_nom IS NULL)", name="anonymat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    code_suivi_empreinte: Mapped[str] = mapped_column(String(64))
    categorie: Mapped[str] = mapped_column(String(30), index=True)
    description: Mapped[str] = mapped_column(String(3000))
    page: Mapped[str | None] = mapped_column(String(300))  # lien, page, cours ou exercice concerné
    anonyme: Mapped[bool] = mapped_column(Boolean)
    auteur_role: Mapped[str | None] = mapped_column(String(12))  # eleve, parent, professeur
    auteur_id: Mapped[int | None] = mapped_column(Integer)
    auteur_nom: Mapped[str | None] = mapped_column(String(120))
    statut: Mapped[str] = mapped_column(String(10), default="recue", index=True)
    priorite: Mapped[str] = mapped_column(String(10), default="normale")
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    reponse: Mapped[str | None] = mapped_column(String(3000))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

    assignee: Mapped["Enseignant | None"] = relationship()


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


class DomainePedagogique(Base):
    """Matière × cycle (Maths lycée, Anglais collège…) : les six domaines existent, chacun s'ouvre à son rythme.

    `actif` : visible de l'équipe pour produire le contenu ; `public` : ouvert aux élèves (CDC V2, EX.1 à EX.4).
    """

    __tablename__ = "domaine_pedagogique"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    matiere: Mapped[str] = mapped_column(String(20))
    cycle: Mapped[str] = mapped_column(String(10))
    libelle: Mapped[str] = mapped_column(String(60))
    niveaux: Mapped[list] = mapped_column(JSON)
    ordre: Mapped[int] = mapped_column(Integer)
    actif: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    public: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Habilitation(Base):
    """Ce qu'un membre de l'équipe peut faire dans un domaine : y enseigner, ou y valider le contenu.

    Un validateur est qualifié matière par matière (CDC V2, EX.9-bis) ; niveau vide = tout le domaine.
    Le rôle d'administrateur reste porté par `enseignant.role` et ne donne pas le droit de valider.
    """

    __tablename__ = "habilitation"
    __table_args__ = (CheckConstraint("role IN ('professeur', 'validateur')", name="ck_habilitation_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    enseignant_id: Mapped[int] = mapped_column(ForeignKey("enseignant.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    domaine_code: Mapped[str] = mapped_column(ForeignKey("domaine_pedagogique.code", ondelete="RESTRICT"))
    niveau: Mapped[str | None] = mapped_column(String(4))
    accordee_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    accordee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())

    enseignant: Mapped[Enseignant] = relationship(foreign_keys=[enseignant_id], back_populates="habilitations")



class RattachementParent(Base):
    """Historique des liens parent-enfant : qui a rattaché ou détaché, et quand (CDC V2, EA.11).

    Supprimé avec le compte parent ou l'élève : l'historique ne survit pas à l'effacement des données.
    """

    __tablename__ = "rattachement_parent"
    __table_args__ = (CheckConstraint("action IN ('ajout', 'retrait')", name="ck_rattachement_parent_action"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id", ondelete="CASCADE"), index=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(10))
    # « Administrateur : Nom » ou « Professeur : Nom » : lisible même si le compte est supprimé ensuite.
    par: Mapped[str] = mapped_column(String(120))
    le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())

    eleve: Mapped[Eleve] = relationship()


class ArchiveInscription(Base):
    """Copie figée d'une inscription (classe de maths ou groupe d'anglais) retirée ou dont la classe a été
    supprimée : séances, réponses et progression restent consultables sur la fiche de l'enfant (V3, Lot 0).

    Seules les inscriptions d'un enfant de famille sont archivées : l'enfant existe toujours. Effacer l'enfant
    (droit à l'effacement) efface ses archives en cascade ; la purge RGPD les supprime aussi à échéance.
    """

    __tablename__ = "archive_inscription"

    id: Mapped[int] = mapped_column(primary_key=True)
    enfant_id: Mapped[int] = mapped_column(ForeignKey("enfant.id", ondelete="CASCADE"), index=True)
    matiere: Mapped[str] = mapped_column(String(20))  # « maths » ou « anglais »
    domaine_code: Mapped[str] = mapped_column(String(30))
    niveau: Mapped[str] = mapped_column(String(4))
    parcours: Mapped[str | None] = mapped_column(String(30))
    # Code de la classe ou nom du groupe, et professeur, tels qu'ils étaient au moment de l'archivage.
    cours: Mapped[str] = mapped_column(String(60))
    enseignant: Mapped[str] = mapped_column(String(100))
    inscrit_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archivee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)
    par: Mapped[str] = mapped_column(String(120))
    motif: Mapped[str] = mapped_column(String(60))
    resume: Mapped[dict] = mapped_column(JSON)
    contenu: Mapped[dict] = mapped_column(JSON)


class SuppressionInterdite(RuntimeError):
    """Une question ne se supprime pas : mettre `archivee = True`."""


@event.listens_for(Session, "before_flush")
def _interdire_suppression_question(session: Session, _contexte, _instances) -> None:
    # Filet côté ORM ; côté base, la clé étrangère RESTRICT protège déjà
    # toute question ayant reçu au moins une réponse.
    if any(isinstance(objet, Question) for objet in session.deleted):
        raise SuppressionInterdite("Une question ne se supprime pas : archivez-la (archivee = True).")
