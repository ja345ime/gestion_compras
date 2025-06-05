#!/usr/bin/env python
"""Script template for Alembic migrations."""
from __future__ import with_statement
from alembic import op
import sqlalchemy as sa

revision = '${up_revision}'
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else 'pass'}


def downgrade():
    ${downgrades if downgrades else 'pass'}
