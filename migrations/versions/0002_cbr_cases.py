"""Persistencia de casos CBR.

Revision ID: 0002_cbr_cases
Revises: 0001_knowledge
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_cbr_cases"
down_revision: str | Sequence[str] | None = "0001_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cbr_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("taxpayer_type", sa.String(length=100), nullable=False),
        sa.Column("activity", sa.String(length=200), nullable=False),
        sa.Column("tax", sa.String(length=100), nullable=False),
        sa.Column("problem_type", sa.String(length=200), nullable=False),
        sa.Column("authority_act", sa.String(length=200), nullable=True),
        sa.Column("procedural_stage", sa.String(length=200), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("resolution_summary", sa.Text(), nullable=False),
        sa.Column("normative_refs", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("anonymized", sa.Boolean(), nullable=False),
        sa.Column("validated", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("case_id"),
    )
    op.create_index("ix_cbr_cases_case_id", "cbr_cases", ["case_id"])
    op.create_index("ix_cbr_cases_status", "cbr_cases", ["status"])
    op.create_index("ix_cbr_cases_taxpayer_type", "cbr_cases", ["taxpayer_type"])
    op.create_index("ix_cbr_cases_tax", "cbr_cases", ["tax"])
    op.create_index("ix_cbr_cases_problem_type", "cbr_cases", ["problem_type"])
    op.create_index("ix_cbr_cases_fiscal_year", "cbr_cases", ["fiscal_year"])


def downgrade() -> None:
    op.drop_index("ix_cbr_cases_fiscal_year", table_name="cbr_cases")
    op.drop_index("ix_cbr_cases_problem_type", table_name="cbr_cases")
    op.drop_index("ix_cbr_cases_tax", table_name="cbr_cases")
    op.drop_index("ix_cbr_cases_taxpayer_type", table_name="cbr_cases")
    op.drop_index("ix_cbr_cases_status", table_name="cbr_cases")
    op.drop_index("ix_cbr_cases_case_id", table_name="cbr_cases")
    op.drop_table("cbr_cases")
