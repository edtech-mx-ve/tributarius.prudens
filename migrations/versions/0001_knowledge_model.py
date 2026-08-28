"""Modelo de conocimiento jurídico-fiscal.

Revision ID: 0001_knowledge
Revises:
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_knowledge"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("authority", sa.String(length=250), nullable=True),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_knowledge_sources_layer", "knowledge_sources", ["layer"])

    op.create_table(
        "legal_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("unit_type", sa.String(length=32), nullable=False),
        sa.Column("identifier", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("matter", sa.String(length=200), nullable=True),
        sa.Column("jurisdiction", sa.String(length=50), nullable=True),
        sa.Column("parent_unit_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_unit_id"], ["legal_units.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_legal_units_source_id", "legal_units", ["source_id"])
    op.create_index("ix_legal_units_unit_type", "legal_units", ["unit_type"])
    op.create_index("ix_legal_units_identifier", "legal_units", ["identifier"])
    op.create_index("ix_legal_units_matter", "legal_units", ["matter"])
    op.create_index("ix_legal_units_jurisdiction", "legal_units", ["jurisdiction"])

    op.create_table(
        "norm_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legal_unit_id", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(length=100), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("validity_status", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["legal_unit_id"], ["legal_units.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_norm_versions_legal_unit_id", "norm_versions", ["legal_unit_id"])
    op.create_index("ix_norm_versions_effective_from", "norm_versions", ["effective_from"])
    op.create_index("ix_norm_versions_effective_to", "norm_versions", ["effective_to"])
    op.create_index("ix_norm_versions_fiscal_year", "norm_versions", ["fiscal_year"])
    op.create_index("ix_norm_versions_validity_status", "norm_versions", ["validity_status"])

    op.create_table(
        "knowledge_relations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_unit_id", sa.Integer(), nullable=False),
        sa.Column("target_unit_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=40), nullable=False),
        sa.Column("rationale", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["source_unit_id"], ["legal_units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_unit_id"], ["legal_units.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_knowledge_relations_source_unit_id",
        "knowledge_relations",
        ["source_unit_id"],
    )
    op.create_index(
        "ix_knowledge_relations_target_unit_id",
        "knowledge_relations",
        ["target_unit_id"],
    )
    op.create_index(
        "ix_knowledge_relations_relation_type",
        "knowledge_relations",
        ["relation_type"],
    )

    op.create_table(
        "master_matrix_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_key", sa.String(length=100), nullable=False),
        sa.Column("module_name", sa.String(length=200), nullable=False),
        sa.Column("prodecon_refs", sa.JSON(), nullable=False),
        sa.Column("unam_refs", sa.JSON(), nullable=False),
        sa.Column("normative_refs", sa.JSON(), nullable=False),
        sa.Column("jurisprudential_refs", sa.JSON(), nullable=False),
        sa.Column("rule_refs", sa.JSON(), nullable=False),
        sa.Column("calculation_refs", sa.JSON(), nullable=False),
        sa.Column("cbr_refs", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("module_key"),
    )
    op.create_index("ix_master_matrix_entries_module_key", "master_matrix_entries", ["module_key"])


def downgrade() -> None:
    op.drop_index("ix_master_matrix_entries_module_key", table_name="master_matrix_entries")
    op.drop_table("master_matrix_entries")
    op.drop_index("ix_knowledge_relations_relation_type", table_name="knowledge_relations")
    op.drop_index("ix_knowledge_relations_target_unit_id", table_name="knowledge_relations")
    op.drop_index("ix_knowledge_relations_source_unit_id", table_name="knowledge_relations")
    op.drop_table("knowledge_relations")
    op.drop_index("ix_norm_versions_validity_status", table_name="norm_versions")
    op.drop_index("ix_norm_versions_fiscal_year", table_name="norm_versions")
    op.drop_index("ix_norm_versions_effective_to", table_name="norm_versions")
    op.drop_index("ix_norm_versions_effective_from", table_name="norm_versions")
    op.drop_index("ix_norm_versions_legal_unit_id", table_name="norm_versions")
    op.drop_table("norm_versions")
    op.drop_index("ix_legal_units_jurisdiction", table_name="legal_units")
    op.drop_index("ix_legal_units_matter", table_name="legal_units")
    op.drop_index("ix_legal_units_identifier", table_name="legal_units")
    op.drop_index("ix_legal_units_unit_type", table_name="legal_units")
    op.drop_index("ix_legal_units_source_id", table_name="legal_units")
    op.drop_table("legal_units")
    op.drop_index("ix_knowledge_sources_layer", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
