from __future__ import with_statement
import logging
from logging.config import fileConfig

from alembic import context
from app import create_app, db

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from app import db

app = create_app()
with app.app_context():
    config.set_main_option(
        'sqlalchemy.url',
        str(db.engine.url).replace('%', '%%')
    )

target_metadata = db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""

    context.configure(
        str(db.engine.url).replace('%', '%%'),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""

    with app.app_context():
        connectable = db.engine


        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
