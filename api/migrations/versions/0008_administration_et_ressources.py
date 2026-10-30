"""administration et ressources (cahier des charges V2 : rôles, journal, versions, liens et PDF)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-30 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('enseignant', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.Enum('enseignant', 'admin', name='role', native_enum=False, create_constraint=True), server_default='enseignant', nullable=False))
        batch_op.add_column(sa.Column('actif', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column('derniere_connexion', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('mdp_provisoire', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('totp_secret', sa.String(length=64), nullable=True))

    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.add_column(sa.Column('masque', sa.Boolean(), server_default=sa.false(), nullable=False))

    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('masque', sa.Boolean(), server_default=sa.false(), nullable=False))

    with op.batch_alter_table('lecon', schema=None) as batch_op:
        batch_op.add_column(sa.Column('modifiee_admin_le', sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auteur', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('modifiee_admin_le', sa.DateTime(timezone=True), nullable=True))

    op.create_table('lecon_version',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lecon_id', sa.Integer(), nullable=False),
    sa.Column('cours', sa.Text(), nullable=False),
    sa.Column('resume', sa.Text(), nullable=False),
    sa.Column('auteur_id', sa.Integer(), nullable=True),
    sa.Column('le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['auteur_id'], ['enseignant.id'], name=op.f('fk_lecon_version_auteur_id_enseignant'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lecon_id'], ['lecon.id'], name=op.f('fk_lecon_version_lecon_id_lecon'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lecon_version'))
    )
    op.create_index(op.f('ix_lecon_version_lecon_id'), 'lecon_version', ['lecon_id'], unique=False)

    op.create_table('journal_admin',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('admin_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('objet', sa.String(length=40), nullable=False),
    sa.Column('objet_id', sa.Integer(), nullable=True),
    sa.Column('avant', sa.JSON(), nullable=True),
    sa.Column('apres', sa.JSON(), nullable=True),
    sa.Column('le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['admin_id'], ['enseignant.id'], name=op.f('fk_journal_admin_admin_id_enseignant'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_journal_admin'))
    )
    op.create_index(op.f('ix_journal_admin_admin_id'), 'journal_admin', ['admin_id'], unique=False)
    op.create_index(op.f('ix_journal_admin_le'), 'journal_admin', ['le'], unique=False)

    op.create_table('ressource',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.Enum('lien', 'pdf', name='type_ressource', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('titre', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=300), server_default='', nullable=False),
    sa.Column('url', sa.String(length=500), nullable=True),
    sa.Column('domaine', sa.String(length=253), nullable=True),
    sa.Column('fichier', sa.String(length=64), nullable=True),
    sa.Column('taille_octets', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=200), nullable=True),
    sa.Column('licence', sa.String(length=100), nullable=True),
    sa.Column('chapitre_id', sa.Integer(), nullable=True),
    sa.Column('competence_id', sa.Integer(), nullable=True),
    sa.Column('portee', sa.Enum('commune', 'classe', name='portee_ressource', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('public', sa.Enum('tous', 'eleves', 'enseignants', name='public_ressource', native_enum=False, create_constraint=True), server_default='tous', nullable=False),
    sa.Column('auteur_id', sa.Integer(), nullable=False),
    sa.Column('masquee', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('motif_masquage', sa.String(length=300), nullable=True),
    sa.Column('echecs_lien', sa.Integer(), server_default='0', nullable=False),
    sa.Column('lien_verifie_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ordre', sa.Integer(), server_default='0', nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('(chapitre_id IS NULL) <> (competence_id IS NULL)', name=op.f('ck_ressource_un_seul_rattachement')),
    sa.CheckConstraint("(type = 'lien') = (url IS NOT NULL)", name=op.f('ck_ressource_url_si_lien')),
    sa.ForeignKeyConstraint(['auteur_id'], ['enseignant.id'], name=op.f('fk_ressource_auteur_id_enseignant'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['chapitre_id'], ['chapitre.id'], name=op.f('fk_ressource_chapitre_id_chapitre'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['competence_id'], ['competence.id'], name=op.f('fk_ressource_competence_id_competence'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ressource')),
    sa.UniqueConstraint('fichier', name=op.f('uq_ressource_fichier'))
    )
    op.create_index(op.f('ix_ressource_auteur_id'), 'ressource', ['auteur_id'], unique=False)
    op.create_index(op.f('ix_ressource_chapitre_id'), 'ressource', ['chapitre_id'], unique=False)
    op.create_index(op.f('ix_ressource_competence_id'), 'ressource', ['competence_id'], unique=False)

    op.create_table('ressource_classe',
    sa.Column('ressource_id', sa.Integer(), nullable=False),
    sa.Column('classe_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['classe_id'], ['classe.id'], name=op.f('fk_ressource_classe_classe_id_classe'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ressource_id'], ['ressource.id'], name=op.f('fk_ressource_classe_ressource_id_ressource'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('ressource_id', 'classe_id', name=op.f('pk_ressource_classe'))
    )

    op.create_table('ressource_consultation',
    sa.Column('ressource_id', sa.Integer(), nullable=False),
    sa.Column('jour', sa.Date(), nullable=False),
    sa.Column('nombre', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['ressource_id'], ['ressource.id'], name=op.f('fk_ressource_consultation_ressource_id_ressource'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('ressource_id', 'jour', name=op.f('pk_ressource_consultation'))
    )

    op.create_table('domaine_interdit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('domaine', sa.String(length=253), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_domaine_interdit')),
    sa.UniqueConstraint('domaine', name=op.f('uq_domaine_interdit_domaine'))
    )


def downgrade() -> None:
    op.drop_table('domaine_interdit')
    op.drop_table('ressource_consultation')
    op.drop_table('ressource_classe')
    op.drop_index(op.f('ix_ressource_competence_id'), table_name='ressource')
    op.drop_index(op.f('ix_ressource_chapitre_id'), table_name='ressource')
    op.drop_index(op.f('ix_ressource_auteur_id'), table_name='ressource')
    op.drop_table('ressource')
    op.drop_index(op.f('ix_journal_admin_le'), table_name='journal_admin')
    op.drop_index(op.f('ix_journal_admin_admin_id'), table_name='journal_admin')
    op.drop_table('journal_admin')
    op.drop_index(op.f('ix_lecon_version_lecon_id'), table_name='lecon_version')
    op.drop_table('lecon_version')

    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_column('modifiee_admin_le')
        batch_op.drop_column('auteur')

    with op.batch_alter_table('lecon', schema=None) as batch_op:
        batch_op.drop_column('modifiee_admin_le')

    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.drop_column('masque')

    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.drop_column('masque')

    # Retirer le CHECK avant la colonne (voir la migration 0006).
    with op.batch_alter_table('enseignant', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_enseignant_role'), type_='check')
        batch_op.drop_column('totp_secret')
        batch_op.drop_column('mdp_provisoire')
        batch_op.drop_column('derniere_connexion')
        batch_op.drop_column('actif')
        batch_op.drop_column('role')
