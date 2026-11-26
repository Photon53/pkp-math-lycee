"""accueil et demandes

Issue #172 — Accueil et demandes : contacts adultes et demandes (Claude) ; utilisé aussi par #171 (candidatures et
partenariats). Tables `contact_adulte` et `demande_accueil` (données d'adultes ; le CV d'une candidature est un fichier hors base,
supprimé avec sa demande). Les demandes de `demande_collaboration` (migration 0046, #171) y sont reprises, avec leur
référence, leur CV, leur traitement et leurs dates, puis cette table est supprimée. Rattachement : un contact par
e-mail normalisé identique, avec les coordonnées de sa demande la plus ancienne.

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-19 21:16:44.324002
"""

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op


revision: str = '0047'
down_revision: str | None = '0046'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('contact_adulte',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('prenom', sa.String(length=60), nullable=False),
    sa.Column('nom', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('telephone', sa.String(length=30), nullable=True),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contact_adulte'))
    )
    with op.batch_alter_table('contact_adulte', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contact_adulte_email'), ['email'], unique=False)

    op.create_table('demande_accueil',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=20), nullable=False),
    sa.Column('contact_id', sa.Integer(), nullable=False),
    sa.Column('categorie', sa.String(length=12), nullable=False),
    sa.Column('origine', sa.String(length=30), nullable=False),
    sa.Column('prenom', sa.String(length=60), nullable=False),
    sa.Column('nom', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('telephone', sa.String(length=30), nullable=True),
    sa.Column('organisation', sa.String(length=150), nullable=True),
    sa.Column('message', sa.String(length=3000), nullable=True),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('cv_fichier', sa.String(length=64), nullable=True),
    sa.Column('cv_taille_octets', sa.Integer(), nullable=True),
    sa.Column('statut', sa.String(length=10), nullable=False),
    sa.Column('issue', sa.String(length=24), nullable=True),
    sa.Column('notes_internes', sa.String(length=3000), nullable=True),
    sa.Column('responsable_id', sa.Integer(), nullable=True),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('maj_le', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("categorie = 'candidature' OR cv_fichier IS NULL", name=op.f('ck_demande_accueil_cv_candidature')),
    sa.CheckConstraint("categorie IN ('famille', 'information', 'candidature', 'partenariat')", name=op.f('ck_demande_accueil_categorie')),
    sa.CheckConstraint("issue IS NULL OR issue <> 'inscription-effective' OR categorie = 'famille'", name=op.f('ck_demande_accueil_inscription_famille')),
    sa.CheckConstraint("issue IS NULL OR issue IN ('suite-demandee', 'inscription-effective', 'refus', 'cloture')", name=op.f('ck_demande_accueil_issue')),
    sa.CheckConstraint("origine IN ('formulaire-collaboration', 'saisie-admin')", name=op.f('ck_demande_accueil_origine')),
    sa.CheckConstraint("statut <> 'traite' OR issue IS NOT NULL", name=op.f('ck_demande_accueil_issue_si_traite')),
    sa.CheckConstraint("statut IN ('nouveau', 'a-traiter', 'traite')", name=op.f('ck_demande_accueil_statut')),
    sa.ForeignKeyConstraint(['contact_id'], ['contact_adulte.id'], name=op.f('fk_demande_accueil_contact_id_contact_adulte'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['responsable_id'], ['enseignant.id'], name=op.f('fk_demande_accueil_responsable_id_enseignant'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_demande_accueil')),
    sa.UniqueConstraint('reference', name=op.f('uq_demande_accueil_reference'))
    )
    with op.batch_alter_table('demande_accueil', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_demande_accueil_categorie'), ['categorie'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_accueil_contact_id'), ['contact_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_accueil_cree_le'), ['cree_le'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_accueil_maj_le'), ['maj_le'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_accueil_statut'), ['statut'], unique=False)



    _reprendre_demandes_de_collaboration()
    with op.batch_alter_table('demande_collaboration', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_type'))
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_statut'))
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_maj_le'))
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_cree_le'))
    op.drop_table('demande_collaboration')


def _reprendre_demandes_de_collaboration() -> None:
    """Copie chaque candidature et chaque partenariat de 0046 dans le socle, sans rien perdre du traitement."""
    connexion = op.get_bind()
    ancienne = sa.table(
        'demande_collaboration', *(sa.column(c) for c in (
            'id', 'reference', 'type', 'prenom', 'nom', 'email', 'telephone', 'matieres', 'niveaux', 'disponibilites',
            'structure_nom', 'structure_type', 'fonction', 'message', 'cv_fichier', 'cv_taille_octets', 'statut', 'issue',
            'notes_internes', 'responsable_id', 'cree_le', 'maj_le',
        ))
    )
    contacts = sa.table('contact_adulte', *(sa.column(c) for c in ('id', 'prenom', 'nom', 'email', 'telephone', 'cree_le')))
    demandes = sa.table('demande_accueil', *(sa.column(c) for c in (
        'reference', 'contact_id', 'categorie', 'origine', 'prenom', 'nom', 'email', 'telephone', 'organisation', 'message',
        'cv_fichier', 'cv_taille_octets', 'statut', 'issue', 'notes_internes', 'responsable_id', 'cree_le', 'maj_le',
    )), sa.column('details', sa.JSON()))
    par_email: dict[str, int] = {}
    for d in connexion.execute(sa.select(ancienne).order_by(ancienne.c.cree_le, ancienne.c.id)).mappings():
        email = "".join(d['email'].split()).lower()
        if email not in par_email:
            par_email[email] = connexion.execute(
                contacts.insert().values(prenom=d['prenom'], nom=d['nom'], email=email, telephone=d['telephone'], cree_le=d['cree_le'])
                .returning(contacts.c.id)
            ).scalar_one()
        if d['type'] == 'candidature':
            details = {
                'matieres': d['matieres'].split(',') if d['matieres'] else [],
                'niveaux': d['niveaux'].split(',') if d['niveaux'] else [],
                'disponibilites': d['disponibilites'],
            }
        else:
            details = {'structure_type': d['structure_type'], 'fonction': d['fonction']}
        connexion.execute(demandes.insert().values(
            reference=d['reference'], contact_id=par_email[email], categorie=d['type'], origine='formulaire-collaboration',
            prenom=d['prenom'], nom=d['nom'], email=email, telephone=d['telephone'], organisation=d['structure_nom'],
            message=d['message'], details=details, cv_fichier=d['cv_fichier'], cv_taille_octets=d['cv_taille_octets'],
            statut=d['statut'], issue=d['issue'], notes_internes=d['notes_internes'], responsable_id=d['responsable_id'],
            cree_le=d['cree_le'], maj_le=d['maj_le'],
        ))


def downgrade() -> None:
    # Recrée `demande_collaboration` (0046) et y remet les candidatures et partenariats. Les demandes des files
    # familles et informations n'existent pas en 0046 : elles sont perdues (sauvegarde préalable obligatoire).
    _migration_0046().upgrade()
    connexion = op.get_bind()
    for d in connexion.execute(sa.text(
        "SELECT * FROM demande_accueil WHERE categorie IN ('candidature', 'partenariat') ORDER BY id"
    )).mappings():
        details = d['details'] if isinstance(d['details'], dict) else json.loads(d['details'] or '{}')
        connexion.execute(sa.text(
            "INSERT INTO demande_collaboration (reference, type, prenom, nom, email, telephone, matieres, niveaux, "
            "disponibilites, structure_nom, structure_type, fonction, message, cv_fichier, cv_taille_octets, statut, issue, "
            "notes_internes, responsable_id, cree_le, maj_le) VALUES (:reference, :type, :prenom, :nom, :email, :telephone, "
            ":matieres, :niveaux, :disponibilites, :structure_nom, :structure_type, :fonction, :message, :cv_fichier, "
            ":cv_taille_octets, :statut, :issue, :notes_internes, :responsable_id, :cree_le, :maj_le)"
        ), {
            'reference': d['reference'], 'type': d['categorie'], 'prenom': d['prenom'], 'nom': d['nom'], 'email': d['email'],
            'telephone': d['telephone'], 'matieres': ','.join(details.get('matieres') or []) or None,
            'niveaux': ','.join(details.get('niveaux') or []) or None, 'disponibilites': details.get('disponibilites'),
            'structure_nom': d['organisation'], 'structure_type': details.get('structure_type'), 'fonction': details.get('fonction'),
            'message': d['message'], 'cv_fichier': d['cv_fichier'], 'cv_taille_octets': d['cv_taille_octets'],
            'statut': d['statut'], 'issue': d['issue'], 'notes_internes': d['notes_internes'],
            'responsable_id': d['responsable_id'], 'cree_le': d['cree_le'], 'maj_le': d['maj_le'],
        })
    with op.batch_alter_table('demande_accueil', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_demande_accueil_statut'))
        batch_op.drop_index(batch_op.f('ix_demande_accueil_maj_le'))
        batch_op.drop_index(batch_op.f('ix_demande_accueil_cree_le'))
        batch_op.drop_index(batch_op.f('ix_demande_accueil_contact_id'))
        batch_op.drop_index(batch_op.f('ix_demande_accueil_categorie'))

    op.drop_table('demande_accueil')
    with op.batch_alter_table('contact_adulte', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_contact_adulte_email'))

    op.drop_table('contact_adulte')


def _migration_0046():
    """Module de la migration 0046, pour recréer sa table à l'identique."""
    chemin = Path(__file__).with_name('0046_demandes_de_collaboration.py')
    spec = importlib.util.spec_from_file_location('migration_0046', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
