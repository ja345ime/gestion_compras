#!/usr/bin/env python
"""Script template for Alembic migrations."""
from __future__ import with_statement
from alembic import op
import sqlalchemy as sa

revision = '884f5f3df5ea'
down_revision = '8c2fcdcf5b5c'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import String
    op.alter_column('usuario', 'password_hash',
        existing_type=sa.String(length=128),
        type_=sa.String(length=512),
        existing_nullable=False
    )


def downgrade():
    op.alter_column('usuario', 'password_hash',
        existing_type=sa.String(length=512),
        type_=sa.String(length=128),
        existing_nullable=False
    )
