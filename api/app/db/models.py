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
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    false,
    func,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.referentiel import (
    SOURCE_PKP,
    Adaptation,
    NatureChapitre,
    Parcours,
    PorteeRessource,
    PublicRessource,
    Role,
    RubriqueFrancais,
    StatutObservation,
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
    __table_args__ = (
        CheckConstraint("mode_correction IN ('apres_chaque_question', 'fin_du_quiz')", name="mode_correction"),
    )

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
    # Issue #162 (lot 3) : le professeur ouvre le diagnostic des acquis antérieurs à ses élèves ; fermé par défaut.
    diagnostic_ouvert: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Issue #217 : mode de correction des quiz de français de la classe (#110, mêmes valeurs que l'anglais).
    mode_correction: Mapped[str] = mapped_column(String(25), default="apres_chaque_question",
                                                 server_default="apres_chaque_question")

    enseignant: Mapped[Enseignant] = relationship(back_populates="classes")
    chapitres_proposes: Mapped[list["Chapitre"]] = relationship(secondary=chapitres_de_classe)
    # Issue #217 : mode de correction propre à un dossier de français, pour cette classe.
    modes_dossiers: Mapped[list["ModeCorrectionDossierFrancais"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )

    def mode_correction_de(self, code: str) -> str:
        """Réglage du dossier, sinon de la classe, sinon le défaut (#110)."""
        from app.correction import mode_effectif

        return mode_effectif(self.mode_correction, next((m.mode for m in self.modes_dossiers if m.code == code), None))
    eleves: Mapped[list["Eleve"]] = relationship(
        back_populates="classe", cascade="all, delete-orphan", passive_deletes=True
    )


class ClassePilote(Base):
    """Classe autorisée à travailler dans un domaine actif mais fermé au public (issue #176, SEC-D6).

    Exception à EX.4, accordée par un administrateur : la trace (qui, quand, pourquoi) reste dans cette table et
    dans le journal. Révoquer l'autorisation coupe l'accès des élèves sans rien supprimer de leur travail.
    """

    __tablename__ = "classe_pilote"

    classe_id: Mapped[int] = mapped_column(ForeignKey("classe.id", ondelete="CASCADE"), primary_key=True)
    accordee_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    accordee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    motif: Mapped[str] = mapped_column(String(200))

    classe: Mapped[Classe] = relationship()
    accordee_par: Mapped["Enseignant | None"] = relationship()


class Redaction(Base):
    """Rédaction d'un élève sur un sujet de français (issue #179, décision RGPD-2).

    Une ligne par version : brouillon (visible de l'élève seul), remise (visible du professeur de la classe),
    corrigée (commentaire du professeur, puis réécriture possible dans une nouvelle version). Conservée jusqu'au
    31 août de l'année scolaire (`conserver_jusqu_au`), puis supprimée par la purge ; supprimée avec l'élève.
    """

    __tablename__ = "redaction"
    __table_args__ = (
        UniqueConstraint("eleve_id", "question_id", "version", name="uq_redaction_eleve_question_version"),
        CheckConstraint("statut IN ('brouillon', 'remise', 'corrigee')", name="statut"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    texte: Mapped[str] = mapped_column(Text, default="")
    statut: Mapped[str] = mapped_column(String(10), default="brouillon")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    remise_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commentaire: Mapped[str | None] = mapped_column(Text)
    corrigee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correcteur_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    conserver_jusqu_au: Mapped[date] = mapped_column(Date, index=True)

    eleve: Mapped["Eleve"] = relationship()
    question: Mapped["Question"] = relationship()
    correcteur: Mapped["Enseignant | None"] = relationship()


class Eleve(Base):
    __tablename__ = "eleve"
    __table_args__ = (
        UniqueConstraint("prenom", "classe_id", name="uq_eleve_prenom_classe"),
        # Identifiant comparé sans casse (« Lina1 » = « lina1 », RGPD-1, #87).
        Index("uq_eleve_identifiant_minuscules", text("lower(identifiant)"), unique=True),
        # Un élève fictif par acteur, rôle d'origine et classe (issue #184).
        UniqueConstraint("simulation_par_id", "simulation_role", "classe_id", name="uq_eleve_simulation"),
        CheckConstraint(
            "(simulation_par_id IS NULL AND simulation_role IS NULL) OR "
            "(simulation_par_id IS NOT NULL AND simulation_role IN ('enseignant', 'admin'))",
            name="simulation",
        ),
    )

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
    # Élève fictif de simulation (issue #184) : propre à un professeur ou un administrateur (`simulation_par_id`,
    # `simulation_role`) et à une classe. Sans identifiant ni code personnel communicable ; masqué de toutes les
    # requêtes ordinaires (listes, statistiques, bilans) par `app.db.simulation`. Vide pour un vrai élève.
    simulation_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="CASCADE"), index=True)
    simulation_role: Mapped[str | None] = mapped_column(String(12))

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
    __table_args__ = (Index("uq_enfant_identifiant_minuscules", text("lower(identifiant)"), unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Prénom seul : un enfant n'a aucun nom de famille (décision RGPD-1, #87). Deux homonymes d'une même classe
    # se distinguent par leur identifiant (« Lina2 »), affiché à la place du prénom.
    prenom: Mapped[str] = mapped_column(String(50))
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


class CompteurIdentifiant(Base):
    """Dernier numéro attribué pour une base d'identifiant (« lina » → 7 : le prochain est « Lina8 »).

    Décision RGPD-1 (#87) : un numéro n'est jamais réattribué, même après suppression ou purge du compte. Aucun
    lien vers un compte, aucune date : la base (prénom normalisé, tronqué) et un nombre, rien d'autre.
    """

    __tablename__ = "compteur_identifiant"

    base: Mapped[str] = mapped_column(String(40), primary_key=True)
    dernier: Mapped[int] = mapped_column(Integer, default=0)


# Ordre d'affichage des niveaux d'anglais ; ceux qui sont ouverts sont les niveaux du domaine (EX.2).
NIVEAUX_ANGLAIS = ("6e", "5e", "4e", "3e", "2nde", "1re", "Tle")


class GroupeAnglais(Base):
    """Groupe PKP Anglais (collège) : séparé des classes de maths, sans parcours ni chapitres (CDC anglais V1.8)."""

    __tablename__ = "groupe_anglais"
    __table_args__ = (
        CheckConstraint("mode_correction IN ('apres_chaque_question', 'fin_du_quiz')", name="mode_correction"),
    )

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
    # Mode de correction des quiz du groupe (#110) : après chaque question (défaut) ou à la fin du quiz.
    mode_correction: Mapped[str] = mapped_column(
        String(25), default="apres_chaque_question", server_default="apres_chaque_question"
    )

    enseignant: Mapped[Enseignant] = relationship(back_populates="groupes_anglais")
    eleves: Mapped[list["EleveAnglais"]] = relationship(
        back_populates="groupe", cascade="all, delete-orphan", passive_deletes=True
    )
    modes_seances: Mapped[list["ModeCorrectionSeanceAnglais"]] = relationship(
        back_populates="groupe", cascade="all, delete-orphan", passive_deletes=True
    )

    def mode_correction_de(self, code: str) -> str:
        """Mode effectif pour une séance : réglage de la séance dans ce groupe, sinon celui du groupe (#110)."""
        from app.correction import mode_effectif

        return mode_effectif(self.mode_correction, next((m.mode for m in self.modes_seances if m.code == code), None))


class ModeCorrectionSeanceAnglais(Base):
    """Mode de correction propre à une séance, pour un groupe (#110) : remplace le mode du groupe."""

    __tablename__ = "mode_correction_seance_anglais"
    __table_args__ = (
        UniqueConstraint("groupe_id", "code", name="uq_mode_correction_seance_anglais_groupe_code"),
        CheckConstraint("mode IN ('apres_chaque_question', 'fin_du_quiz')", name="mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    groupe_id: Mapped[int] = mapped_column(ForeignKey("groupe_anglais.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(10))
    mode: Mapped[str] = mapped_column(String(25))

    groupe: Mapped[GroupeAnglais] = relationship(back_populates="modes_seances")


class EleveAnglais(Base):
    """Élève d'un groupe d'anglais : un prénom, rien d'autre."""

    __tablename__ = "eleve_anglais"
    __table_args__ = (
        UniqueConstraint("prenom", "groupe_id", name="uq_eleve_anglais_prenom_groupe"),
        Index("uq_eleve_anglais_identifiant_minuscules", text("lower(identifiant)"), unique=True),
    )

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
    reponses: Mapped[list["ReponseAnglais"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


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
    # Score du premier essai, figé (#110, choix B) ; inconnu (None) pour les résultats antérieurs.
    premier_score: Mapped[int | None] = mapped_column(Integer)
    # Un niveau par phrase « I can » : non_observe, avec_aide, en_cours, autonome.
    i_can: Mapped[list] = mapped_column(JSON, default=list)
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, onupdate=_maintenant)

    eleve: Mapped[EleveAnglais] = relationship(back_populates="progression")


class ReponseAnglais(Base):
    """Réponse d'un élève à une question d'un quiz d'anglais, par essai (#110).

    Unique par (élève, séance, essai, question) : la première réponse d'un essai compte et ne se modifie pas.
    """

    __tablename__ = "reponse_anglais"
    __table_args__ = (
        UniqueConstraint("eleve_id", "code", "essai", "question", name="uq_reponse_anglais_eleve_code_essai_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve_anglais.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(10))
    essai: Mapped[int] = mapped_column(Integer)  # 1 = premier essai
    question: Mapped[int] = mapped_column(Integer)  # rang dans le quiz complet, à partir de 0
    choix: Mapped[int] = mapped_column(Integer)
    juste: Mapped[bool] = mapped_column(Boolean)
    repondu_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)


STATUTS_DOSSIER_FRANCAIS = ("brouillon", "soumis", "valide", "refuse", "archive")


class DossierFrancais(Base):
    """Dossier de français (leçon, textes, questions et supports professeur), importé de contenu/francais (#98).

    Même circuit que les séances d'anglais : version courante = la dernière ; version validée = la dernière validée,
    seule servie aux élèves, et seulement dans les classes auxquelles le professeur l'a ouvert (#212, SEC-D6).
    """

    __tablename__ = "dossier_francais"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    domaine_code: Mapped[str] = mapped_column(ForeignKey("domaine_pedagogique.code", ondelete="RESTRICT"), index=True)
    niveau: Mapped[str] = mapped_column(String(4))
    titre: Mapped[str] = mapped_column(String(200))

    versions: Mapped[list["DossierFrancaisVersion"]] = relationship(
        back_populates="dossier", cascade="all, delete-orphan", passive_deletes=True,
        order_by="DossierFrancaisVersion.numero",
    )
    # Classes auxquelles un professeur l'a ouvert (#212) ; seule la version validée leur est servie.
    ouvertures: Mapped[list["OuvertureDossierFrancais"]] = relationship(
        back_populates="dossier", cascade="all, delete-orphan", passive_deletes=True,
    )

    @property
    def courante(self) -> "DossierFrancaisVersion":
        return self.versions[-1]

    @property
    def validee(self) -> "DossierFrancaisVersion | None":
        return next((v for v in reversed(self.versions) if v.statut == "valide"), None)


class DossierFrancaisVersion(Base):
    """Une version importée : partie élève et partie professeur séparées, empreinte du fichier source."""

    __tablename__ = "dossier_francais_version"
    __table_args__ = (
        UniqueConstraint("dossier_id", "numero", name="uq_dossier_francais_version_numero"),
        # Import idempotent : un même fichier source ne crée jamais deux versions d'un dossier.
        UniqueConstraint("dossier_id", "empreinte", name="uq_dossier_francais_version_empreinte"),
        CheckConstraint(
            "statut IN ('brouillon', 'soumis', 'valide', 'refuse', 'archive')", name="ck_dossier_francais_version_statut"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossier_francais.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    # Partie élève (leçon, textes, consignes) et partie professeur (corrigés, déroulement, grille) : jamais mélangées.
    eleve: Mapped[dict] = mapped_column(JSON)
    professeur: Mapped[dict] = mapped_column(JSON)
    # Quiz corrigé automatiquement (#217, comme l'anglais) : questions, choix, bonne réponse et explication. Jamais
    # transmis à l'élève avant sa réponse (ARCH-4) : la vue élève n'en garde que les questions et les choix.
    quiz: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    # Format, attribution, registre des sources, cible et codes locaux.
    meta: Mapped[dict] = mapped_column(JSON)
    empreinte: Mapped[str] = mapped_column(String(64))
    statut: Mapped[str] = mapped_column(String(10), default="soumis")
    # Auteur vide = contenu importé du dépôt (rédaction par un agent, voir meta.attribution).
    auteur_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    validateur_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    decide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motif_refus: Mapped[str | None] = mapped_column(Text)

    dossier: Mapped[DossierFrancais] = relationship(back_populates="versions")
    auteur: Mapped["Enseignant | None"] = relationship(foreign_keys=[auteur_id])
    validateur: Mapped["Enseignant | None"] = relationship(foreign_keys=[validateur_id])


class OuvertureDossierFrancais(Base):
    """Dossier de français ouvert par le professeur à l'une de ses classes (#212, même circuit que l'anglais).

    Seule la version validée du dossier est servie aux élèves, et seulement si la classe y a accès (classe pilote
    d'un domaine fermé, SEC-D6). Une révision soumise ou refusée ne remplace pas la version validée diffusée.
    """

    __tablename__ = "ouverture_dossier_francais"

    classe_id: Mapped[int] = mapped_column(ForeignKey("classe.id", ondelete="CASCADE"), primary_key=True)
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossier_francais.id", ondelete="CASCADE"), primary_key=True, index=True)
    ouvert_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    ouvert_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())

    classe: Mapped[Classe] = relationship()
    dossier: Mapped[DossierFrancais] = relationship(back_populates="ouvertures")
    ouvert_par: Mapped["Enseignant | None"] = relationship()


class ModeCorrectionDossierFrancais(Base):
    """Mode de correction propre à un dossier, pour une classe (#217, #110) : remplace le mode de la classe."""

    __tablename__ = "mode_correction_dossier_francais"
    __table_args__ = (
        UniqueConstraint("classe_id", "code", name="uq_mode_correction_dossier_francais_classe_code"),
        CheckConstraint("mode IN ('apres_chaque_question', 'fin_du_quiz')", name="mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    classe_id: Mapped[int] = mapped_column(ForeignKey("classe.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    mode: Mapped[str] = mapped_column(String(25))


class ProgressionFrancais(Base):
    """Résultat d'un élève sur un dossier de français (#217, comme `ProgressionAnglais`) : quiz et auto-évaluation."""

    __tablename__ = "progression_francais"
    __table_args__ = (UniqueConstraint("eleve_id", "code", name="uq_progression_francais_eleve_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    meilleur_score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    tentatives: Mapped[int] = mapped_column(Integer, default=0)
    premier_score: Mapped[int | None] = mapped_column(Integer)  # score du premier essai, figé (#110)
    # Un niveau par phrase « Je sais » du dossier : non_observe, avec_aide, en_cours, autonome (comme « I can »).
    auto_evaluation: Mapped[list] = mapped_column(JSON, default=list)
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, onupdate=_maintenant)


class ReponseQuizFrancais(Base):
    """Réponse à une question du quiz d'un dossier, par essai (#217, comme `ReponseAnglais`) ; non modifiable."""

    __tablename__ = "reponse_quiz_francais"
    __table_args__ = (
        UniqueConstraint("eleve_id", "code", "essai", "question", name="uq_reponse_quiz_francais_eleve_code_essai_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    essai: Mapped[int] = mapped_column(Integer)
    question: Mapped[int] = mapped_column(Integer)
    choix: Mapped[int] = mapped_column(Integer)
    juste: Mapped[bool] = mapped_column(Boolean)
    repondu_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)


class ReponseRedigeeFrancais(Base):
    """Réponse rédigée d'un élève à une question d'un dossier, avec le retour du professeur (#217, RGPD-2).

    Mêmes règles que les rédactions (#179) : brouillon visible de l'élève seul ; remise visible du professeur de la
    classe ; retour du professeur ; conservée jusqu'au 31 août de l'année scolaire, supprimée avec l'élève, purgée
    30 jours après l'archivage de la classe, incluse dans l'export RGPD ; fermée tant que `PKP_REDACTION_ACTIVE` est faux.
    """

    __tablename__ = "reponse_redigee_francais"
    __table_args__ = (
        UniqueConstraint("eleve_id", "code", "question", name="uq_reponse_redigee_francais_eleve_code_question"),
        CheckConstraint("statut IN ('brouillon', 'remise', 'corrigee')", name="statut"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    question: Mapped[str] = mapped_column(String(10))
    texte: Mapped[str] = mapped_column(Text, default="")
    statut: Mapped[str] = mapped_column(String(10), default="brouillon")
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, server_default=func.now())
    remise_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commentaire: Mapped[str | None] = mapped_column(Text)
    corrigee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correcteur_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    conserver_jusqu_au: Mapped[date] = mapped_column(Date, index=True)

    eleve: Mapped["Eleve"] = relationship()


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
    # Issue #162 : un chapitre de diagnostic n'est jamais ouvert à une classe ni servi en séance d'entraînement.
    nature: Mapped[NatureChapitre] = mapped_column(
        _enum(NatureChapitre, "nature_chapitre"), default=NatureChapitre.APPRENTISSAGE,
        server_default=NatureChapitre.APPRENTISSAGE.value,
    )
    # Diagnostic : parcours des classes concernées, programme de l'année précédente interrogé.
    publics: Mapped[list | None] = mapped_column(JSON)
    programme_prerequis: Mapped[str | None] = mapped_column(String(40))
    # Issue #177 : rubrique d'un chapitre de français ; vide pour les maths.
    rubrique: Mapped[RubriqueFrancais | None] = mapped_column(_enum(RubriqueFrancais, "rubrique_francais"))

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
    # Diagnostic (#162) : compétences du diagnostic du niveau précédent, ouvertes si celle-ci est à reprendre.
    retour: Mapped[list | None] = mapped_column(JSON)

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


class PassationDiagnostic(Base):
    """Une passation du diagnostic par un élève (issue #162, lot 3) : une question à la fois, servie par le serveur,
    sans correction affichée. Une seule passation par inscription ; elle se reprend tant qu'elle n'est pas finie."""

    __tablename__ = "passation_diagnostic"

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True, unique=True)
    debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    question_courante_id: Mapped[int | None] = mapped_column(ForeignKey("question.id", ondelete="RESTRICT"))
    question_servie_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    eleve: Mapped["Eleve"] = relationship()
    question_courante: Mapped["Question | None"] = relationship()
    observations: Mapped[list["ObservationDiagnostic"]] = relationship(
        back_populates="passation", order_by="ObservationDiagnostic.id"
    )


class ObservationDiagnostic(Base):
    """Réponse d'un élève à une question de diagnostic (issue #162).

    Table distincte de `reponse` : le taux de maîtrise, calculé sur `reponse`, ne voit jamais le diagnostic.
    Une réponse rédigée reste « en attente de correction » jusqu'à la décision d'un professeur.
    """

    __tablename__ = "observation_diagnostic"

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    passation_id: Mapped[int | None] = mapped_column(ForeignKey("passation_diagnostic.id", ondelete="CASCADE"), index=True)
    duree_s: Mapped[float | None] = mapped_column(Float)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="RESTRICT"), index=True)
    reponse_donnee: Mapped[str] = mapped_column(Text)
    statut: Mapped[StatutObservation] = mapped_column(_enum(StatutObservation, "statut_observation"), index=True)
    observe_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)
    corrige_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    corrige_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    eleve: Mapped["Eleve"] = relationship()
    question: Mapped[Question] = relationship()
    corrige_par: Mapped["Enseignant | None"] = relationship()
    passation: Mapped["PassationDiagnostic | None"] = relationship(back_populates="observations")


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


class ContactAdulte(Base):
    """Adulte qui a pris contact avec Boussole hors de tout compte (issue #172, « Accueil et demandes »).

    Un contact porte une ou plusieurs demandes, chacune avec sa catégorie, son statut et son historique. **Ce n'est
    ni un compte, ni un parent, ni un inscrit** : aucun enfant, aucun accès, aucune donnée pédagogique n'y est relié.
    Une nouvelle demande n'est rattachée à un contact existant que si l'e-mail normalisé (minuscules, sans espaces)
    est identique ; les coordonnées saisies restent sur la demande et n'écrasent jamais celles du contact.
    """

    __tablename__ = "contact_adulte"

    id: Mapped[int] = mapped_column(primary_key=True)
    prenom: Mapped[str] = mapped_column(String(60))
    nom: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), index=True)  # normalisé : minuscules, sans espaces
    telephone: Mapped[str | None] = mapped_column(String(30))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

    demandes: Mapped[list["DemandeAccueil"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", order_by="DemandeAccueil.cree_le"
    )


class DemandeAccueil(Base):
    """Demande d'un contact adulte, rangée dans une file d'« Accueil et demandes » (issues #172, #171).

    Files : familles et préinscriptions, informations et questions, candidatures de professeurs, partenariats de
    structures. Une demande ne vaut ni inscription, ni compte, ni habilitation, ni contrat ; son issue est explicite.
    Les champs propres à la catégorie (matières d'un candidat, type de structure…) sont dans `details`, validés à
    l'entrée par l'API. Le CV d'une candidature est un fichier hors base (`app.collaboration`), supprimé avec elle.
    """

    __tablename__ = "demande_accueil"
    __table_args__ = (
        CheckConstraint("categorie IN ('famille', 'information', 'candidature', 'partenariat')", name="categorie"),
        CheckConstraint("origine IN ('formulaire-collaboration', 'saisie-admin')", name="origine"),
        CheckConstraint("statut IN ('nouveau', 'a-traiter', 'traite')", name="statut"),
        CheckConstraint(
            "issue IS NULL OR issue IN ('suite-demandee', 'inscription-effective', 'refus', 'cloture')", name="issue"
        ),
        CheckConstraint("statut <> 'traite' OR issue IS NOT NULL", name="issue_si_traite"),
        CheckConstraint("issue IS NULL OR issue <> 'inscription-effective' OR categorie = 'famille'", name="inscription_famille"),
        CheckConstraint("categorie = 'candidature' OR cv_fichier IS NULL", name="cv_candidature"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contact_adulte.id", ondelete="CASCADE"), index=True)
    categorie: Mapped[str] = mapped_column(String(12), index=True)
    origine: Mapped[str] = mapped_column(String(30))  # d'où vient la demande, dans Boussole
    # Coordonnées telles que saisies avec cette demande (le contact garde les siennes).
    prenom: Mapped[str] = mapped_column(String(60))
    nom: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254))
    telephone: Mapped[str | None] = mapped_column(String(30))
    organisation: Mapped[str | None] = mapped_column(String(150))  # nom de la structure, pour un partenariat
    message: Mapped[str | None] = mapped_column(String(3000))  # besoin, message ou partenariat envisagé
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    cv_fichier: Mapped[str | None] = mapped_column(String(64))  # nom aléatoire sur disque, jamais exposé
    cv_taille_octets: Mapped[int | None] = mapped_column(Integer)
    statut: Mapped[str] = mapped_column(String(10), default="nouveau", index=True)
    issue: Mapped[str | None] = mapped_column(String(24))
    notes_internes: Mapped[str | None] = mapped_column(String(3000))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)
    maj_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)

    contact: Mapped["ContactAdulte"] = relationship(back_populates="demandes")
    responsable: Mapped["Enseignant | None"] = relationship()


class DemandeAide(Base):
    """« Je n'ai pas compris » d'un élève (ticket #28), sur un cours, un exercice ou sa correction.

    Pour un cours, chaque avis (« J'ai compris » / « Je n'ai pas compris ») ajoute une ligne : l'avis courant est
    la ligne la plus récente de l'élève pour cette compétence, l'historique des changements d'avis est conservé.
    Le professeur marque une demande « prise en charge » puis « résolue » sans rien effacer.
    C'est une auto-déclaration de l'élève : elle ne change pas la maîtrise mesurée.
    """

    __tablename__ = "demande_aide"
    __table_args__ = (
        CheckConstraint("objet IN ('cours', 'exercice', 'corrige')", name="objet"),
        CheckConstraint("statut IN ('compris', 'ouverte', 'prise-en-charge', 'resolue')", name="statut"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("eleve.id", ondelete="CASCADE"), index=True)
    competence_id: Mapped[int] = mapped_column(ForeignKey("competence.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"))
    seance_id: Mapped[int | None] = mapped_column(ForeignKey("seance.id", ondelete="SET NULL"))
    objet: Mapped[str] = mapped_column(String(10))
    # « compris » : avis positif sur un cours (aucune demande) ; sinon une demande et son suivi.
    statut: Mapped[str] = mapped_column(String(20))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)
    traitee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    traitee_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))

    eleve: Mapped["Eleve"] = relationship()
    competence: Mapped["Competence"] = relationship()
    question: Mapped["Question | None"] = relationship()
    traitee_par: Mapped["Enseignant | None"] = relationship()


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


class CompteServiceIA(Base):
    """Compte de service du vérificateur IA (ticket #48), distinct des comptes humains.

    Seule l'empreinte HMAC du jeton est conservée : le jeton est montré une fois à l'administrateur, qui le range dans
    le gestionnaire de secrets du service IA. Durée limitée, révocation et renouvellement par un administrateur.
    Le jeton n'ouvre que les routes /service-ia : lecture des exercices demandés et dépôt des rapports.
    """

    __tablename__ = "compte_service_ia"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(80))
    empreinte: Mapped[str] = mapped_column(String(64), unique=True)
    prefixe: Mapped[str] = mapped_column(String(24))  # début du jeton, pour le reconnaître sans le révéler
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)
    cree_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoque_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoque_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    dernier_usage_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PrevalidationIA(Base):
    """Une demande de prévalidation IA d'un exercice, puis son rapport (ticket #48).

    Distincte de la validation pédagogique humaine : elle ne change jamais `Question.statut_validation`, ni le contenu.
    `version` est l'empreinte du contenu examiné : si l'exercice change ensuite, le rapport devient obsolète.
    """

    __tablename__ = "prevalidation_ia"
    __table_args__ = (
        CheckConstraint("statut IN ('en-attente', 'terminee', 'annulee')", name="statut"),
        CheckConstraint(
            "resultat IS NULL OR resultat IN ('aucune-anomalie', 'a-revoir', 'erreur-detectee', 'incertain')",
            name="resultat",
        ),
        CheckConstraint("verite_humaine IS NULL OR verite_humaine IN ('erronee', 'correcte')", name="verite_humaine"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"), index=True)
    lot: Mapped[str] = mapped_column(String(24), index=True)
    version: Mapped[str] = mapped_column(String(64))
    # Exemplaire examiné d'une question à valeurs variables : le même pour l'énoncé et pour le corrigé.
    tirage: Mapped[dict | None] = mapped_column(JSON)
    statut: Mapped[str] = mapped_column(String(12), default="en-attente", index=True)
    resultat: Mapped[str | None] = mapped_column(String(20))
    demandee_par_id: Mapped[int | None] = mapped_column(ForeignKey("enseignant.id", ondelete="SET NULL"))
    demandee_par_nom: Mapped[str] = mapped_column(String(100))
    demandee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)
    compte_service_id: Mapped[int | None] = mapped_column(ForeignKey("compte_service_ia.id", ondelete="SET NULL"))
    enonce_lu_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    corrige_lu_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rendue_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modele: Mapped[str | None] = mapped_column(String(100))
    version_modele: Mapped[str | None] = mapped_column(String(100))
    rapport: Mapped[dict | None] = mapped_column(JSON)
    # Essai sur un lot relu par des professeurs : l'exercice était-il réellement erroné ? Mesure des erreurs non détectées.
    verite_humaine: Mapped[str | None] = mapped_column(String(10))
    verite_commentaire: Mapped[str | None] = mapped_column(String(1000))
    verite_par_nom: Mapped[str | None] = mapped_column(String(100))
    verite_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    question: Mapped["Question"] = relationship()
    compte_service: Mapped["CompteServiceIA | None"] = relationship()


class AccesServiceIA(Base):
    """Journal des appels du compte de service IA, acceptés ou refusés (ticket #48)."""

    __tablename__ = "acces_service_ia"

    id: Mapped[int] = mapped_column(primary_key=True)
    compte_service_id: Mapped[int | None] = mapped_column(ForeignKey("compte_service_ia.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    prevalidation_id: Mapped[int | None] = mapped_column(Integer)
    code_http: Mapped[int] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(45))
    le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True)


class SuppressionInterdite(RuntimeError):
    """Une question ne se supprime pas : mettre `archivee = True`."""


@event.listens_for(Session, "before_flush")
def _interdire_suppression_question(session: Session, _contexte, _instances) -> None:
    # Filet côté ORM ; côté base, la clé étrangère RESTRICT protège déjà
    # toute question ayant reçu au moins une réponse.
    if any(isinstance(objet, Question) for objet in session.deleted):
        raise SuppressionInterdite("Une question ne se supprime pas : archivez-la (archivee = True).")


# Masque les élèves fictifs (issue #184) de toutes les requêtes : importé ici pour être toujours actif.
from app.db import simulation as _simulation  # noqa: E402, F401
